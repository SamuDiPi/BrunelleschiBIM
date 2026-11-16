"""OpenGL 3.3 core renderer of a ``Scene``, using Qt's OpenGL classes only (ADR 0008).

It needs a current OpenGL context: the one of a ``QOpenGLWidget`` on screen, or an
off-screen surface for captures and tests (``render_offscreen``), which opens no window.
"""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray
from PySide6.QtGui import (
    QImage,
    QMatrix4x4,
    QOffscreenSurface,
    QOpenGLContext,
    QSurfaceFormat,
)
from PySide6.QtOpenGL import (
    QOpenGLBuffer,
    QOpenGLFramebufferObject,
    QOpenGLFramebufferObjectFormat,
    QOpenGLShader,
    QOpenGLShaderProgram,
    QOpenGLVertexArrayObject,
)

from brunelleschi.gui.scene3d import FLOATS_PER_VERTEX, Scene

# OpenGL constants used here (PySide6 has no module of GL enums).
GL_FLOAT = 0x1406
GL_TRIANGLES = 0x0004
GL_DEPTH_TEST = 0x0B71
GL_MULTISAMPLE = 0x809D
GL_COLOR_BUFFER_BIT = 0x4000
GL_DEPTH_BUFFER_BIT = 0x0100

VERTEX = """#version 330 core
layout(location = 0) in vec3 position;
layout(location = 1) in vec3 normal;
layout(location = 2) in vec3 colour;
layout(location = 3) in float element;
uniform mat4 mvp;
out vec3 v_colour;
out vec3 v_normal;
flat out float v_element;
void main() {
    gl_Position = mvp * vec4(position, 1.0);
    v_colour = colour;
    v_normal = normal;
    v_element = element;
}
"""

FRAGMENT = """#version 330 core
in vec3 v_colour;
in vec3 v_normal;
flat in float v_element;
uniform float selected;
out vec4 fragment;
void main() {
    vec3 light = normalize(vec3(0.35, -0.55, 0.75));
    float diffuse = abs(dot(normalize(v_normal), light));
    vec3 colour = v_colour * (0.45 + 0.55 * diffuse);
    if (abs(v_element - selected) < 0.5) {
        colour = mix(colour, vec3(0.12, 0.44, 0.82), 0.55);
    }
    fragment = vec4(colour, 1.0);
}
"""

BACKGROUND = (0.97, 0.97, 0.96, 1.0)


def surface_format() -> QSurfaceFormat:
    fmt = QSurfaceFormat()
    fmt.setVersion(3, 3)
    fmt.setProfile(QSurfaceFormat.OpenGLContextProfile.CoreProfile)
    fmt.setDepthBufferSize(24)
    fmt.setSamples(4)
    return fmt


def qmatrix(m: NDArray[np.float64]) -> QMatrix4x4:
    return QMatrix4x4(*[float(v) for v in m.reshape(-1)])  # row-major, as numpy


class Renderer:
    def __init__(self) -> None:
        self.program: QOpenGLShaderProgram | None = None
        self.vao = QOpenGLVertexArrayObject()
        self.vbo = QOpenGLBuffer(QOpenGLBuffer.Type.VertexBuffer)
        self.count = 0
        self.error: str | None = None

    def initialize(self) -> bool:
        """Compile the shaders. False (and ``error``) if OpenGL 3.3 is not available."""
        program = QOpenGLShaderProgram()
        ok = program.addShaderFromSourceCode(QOpenGLShader.ShaderTypeBit.Vertex, VERTEX)
        ok = ok and program.addShaderFromSourceCode(QOpenGLShader.ShaderTypeBit.Fragment, FRAGMENT)
        ok = ok and program.link()
        if not ok:
            self.error = program.log() or "OpenGL 3.3 shaders could not be compiled"
            return False
        self.program = program
        self.vao.create()
        self.vbo.create()
        return True

    def upload(self, scene: Scene) -> None:
        if self.program is None:
            return
        data = np.ascontiguousarray(scene.data, dtype=np.float32)
        self.count = len(data)
        self.vao.bind()
        self.vbo.bind()
        self.vbo.allocate(data.tobytes(), data.nbytes)
        stride = FLOATS_PER_VERTEX * 4
        self.program.bind()
        for location, (size, offset) in enumerate(((3, 0), (3, 3), (3, 6), (1, 9))):
            self.program.enableAttributeArray(location)
            self.program.setAttributeBuffer(location, GL_FLOAT, offset * 4, size, stride)
        self.vbo.release()
        self.vao.release()

    def draw(self, matrix: NDArray[np.float64], width: int, height: int, selected: int) -> None:
        gl = QOpenGLContext.currentContext().functions()
        gl.glViewport(0, 0, width, height)
        gl.glClearColor(*BACKGROUND)
        gl.glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        if self.program is None or self.count == 0:
            return
        gl.glEnable(GL_DEPTH_TEST)
        gl.glEnable(GL_MULTISAMPLE)
        self.program.bind()
        self.program.setUniformValue(self.program.uniformLocation("mvp"), qmatrix(matrix))
        self.program.setUniformValue1f(self.program.uniformLocation("selected"), float(selected))
        self.vao.bind()
        gl.glDrawArrays(GL_TRIANGLES, 0, self.count)
        self.vao.release()


_GL_CHECKED: list[str | None] = []


def gl_unavailable_reason() -> str | None:
    """None if an OpenGL 3.3 core context can be created here, else why not (cached)."""
    if not _GL_CHECKED:
        context = QOpenGLContext()
        context.setFormat(surface_format())
        if not context.create():
            _GL_CHECKED.append("this system cannot create an OpenGL 3.3 context")
        elif (context.format().majorVersion(), context.format().minorVersion()) < (3, 3):
            version = f"{context.format().majorVersion()}.{context.format().minorVersion()}"
            _GL_CHECKED.append(f"OpenGL 3.3 is needed, this system offers {version}")
        else:
            _GL_CHECKED.append(None)
    return _GL_CHECKED[0]


def render_offscreen(
    scene: Scene, matrix: NDArray[np.float64], width: int, height: int, selected: int = -1
) -> QImage | None:
    """Draw a scene into an image without any window. None if OpenGL 3.3 is unavailable
    (for example on Qt's "offscreen" platform, or software-only drivers)."""
    context = QOpenGLContext()
    context.setFormat(surface_format())
    if not context.create():
        return None
    surface = QOffscreenSurface()
    surface.setFormat(context.format())
    surface.create()
    if not context.makeCurrent(surface):
        return None
    fbo_format = QOpenGLFramebufferObjectFormat()
    fbo_format.setAttachment(QOpenGLFramebufferObject.Attachment.Depth)
    fbo_format.setSamples(4)
    fbo = QOpenGLFramebufferObject(width, height, fbo_format)
    fbo.bind()
    renderer = Renderer()
    if not renderer.initialize():
        context.doneCurrent()
        return None
    renderer.upload(scene)
    renderer.draw(matrix, width, height, selected)
    image = fbo.toImage()
    fbo.release()
    context.doneCurrent()
    return image
