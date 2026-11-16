"""Probe B: our own OpenGL 3.3 renderer in a Qt context, off screen (no window).

One vertex buffer for the whole scene (flat normals, colour, element index), a shaded
pass, and a picking pass that writes element indices as colours.
"""

import ctypes
import sys
import time

import numpy as np
from OpenGL import GL
from PySide6.QtGui import QGuiApplication, QOffscreenSurface, QOpenGLContext, QSurfaceFormat
from PySide6.QtOpenGL import QOpenGLFramebufferObject, QOpenGLFramebufferObjectFormat

from meshes import grid, house, triangulate

W, H = 1280, 800

VERTEX = """#version 330 core
layout(location=0) in vec3 pos; layout(location=1) in vec3 nrm;
layout(location=2) in vec3 col; layout(location=3) in float idx;
uniform mat4 mvp; uniform int picking;
out vec3 vcol; flat out float vidx;
void main(){
  gl_Position = mvp * vec4(pos, 1.0);
  float light = 0.45 + 0.55 * max(dot(normalize(nrm), normalize(vec3(0.4, -0.6, 0.8))), 0.0);
  vcol = col * light; vidx = idx;
}"""
FRAGMENT = """#version 330 core
in vec3 vcol; flat in float vidx; uniform int picking; out vec4 frag;
void main(){
  if (picking == 1) {
    int i = int(vidx) + 1;
    frag = vec4(float(i & 255) / 255.0, float((i >> 8) & 255) / 255.0, float((i >> 16) & 255) / 255.0, 1.0);
  } else { frag = vec4(vcol, 1.0); }
}"""


def look_at(eye, target, up):
    f = target - eye
    f /= np.linalg.norm(f)
    s = np.cross(f, up)
    s /= np.linalg.norm(s)
    u = np.cross(s, f)
    m = np.identity(4)
    m[0, :3], m[1, :3], m[2, :3] = s, u, -f
    m[:3, 3] = -m[:3, :3] @ eye
    return m


def perspective(fovy, aspect, near, far):
    f = 1 / np.tan(np.radians(fovy) / 2)
    m = np.zeros((4, 4))
    m[0, 0], m[1, 1] = f / aspect, f
    m[2, 2], m[2, 3] = (far + near) / (near - far), 2 * far * near / (near - far)
    m[3, 2] = -1
    return m


def build_buffer(meshes):
    chunks = []
    for i, m in enumerate(meshes):
        tri = m.vertices[m.faces]  # (n, 3, 3)
        normals = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
        normals /= np.linalg.norm(normals, axis=1, keepdims=True) + 1e-12
        n = len(tri) * 3
        data = np.empty((n, 10), np.float32)
        data[:, 0:3] = tri.reshape(-1, 3)
        data[:, 3:6] = np.repeat(normals, 3, axis=0)
        data[:, 6:9] = m.colour
        data[:, 9] = i
        chunks.append(data)
    return np.concatenate(chunks)


def compile_program():
    prog = GL.glCreateProgram()
    for kind, src in ((GL.GL_VERTEX_SHADER, VERTEX), (GL.GL_FRAGMENT_SHADER, FRAGMENT)):
        sh = GL.glCreateShader(kind)
        GL.glShaderSource(sh, src)
        GL.glCompileShader(sh)
        if not GL.glGetShaderiv(sh, GL.GL_COMPILE_STATUS):
            raise RuntimeError(GL.glGetShaderInfoLog(sh))
        GL.glAttachShader(prog, sh)
    GL.glLinkProgram(prog)
    return prog


def run(name, project, out, ctx, surface):
    meshes, stats = triangulate(project)
    t = time.perf_counter()
    ctx.makeCurrent(surface)
    fmt = QOpenGLFramebufferObjectFormat()
    fmt.setAttachment(QOpenGLFramebufferObject.Attachment.Depth)
    fbo = QOpenGLFramebufferObject(W, H, fmt)
    fbo.bind()
    prog = compile_program()
    data = build_buffer(meshes)
    vao = GL.glGenVertexArrays(1)
    GL.glBindVertexArray(vao)
    vbo = GL.glGenBuffers(1)
    GL.glBindBuffer(GL.GL_ARRAY_BUFFER, vbo)
    GL.glBufferData(GL.GL_ARRAY_BUFFER, data.nbytes, data, GL.GL_STATIC_DRAW)
    for loc, (size, off) in enumerate(((3, 0), (3, 3), (3, 6), (1, 9))):
        GL.glEnableVertexAttribArray(loc)
        GL.glVertexAttribPointer(loc, size, GL.GL_FLOAT, False, 40, ctypes.c_void_p(off * 4))
    build = time.perf_counter() - t

    pts = data[:, :3]
    lo, hi = pts.min(axis=0), pts.max(axis=0)
    centre, radius = (lo + hi) / 2, np.linalg.norm(hi - lo) / 2

    def mvp(angle):
        a = np.radians(angle)
        direction = np.array([np.cos(a) - np.sin(a), np.sin(a) + np.cos(a), 1.1])
        eye = centre + direction / np.linalg.norm(direction) * radius * 3.0
        return perspective(30, W / H, radius * 0.1, radius * 10) @ look_at(eye, centre, np.array([0, 0, 1.0]))

    def draw(matrix, picking=0):
        GL.glViewport(0, 0, W, H)
        GL.glEnable(GL.GL_DEPTH_TEST)
        GL.glClearColor(1, 1, 1, 1) if not picking else GL.glClearColor(0, 0, 0, 1)
        GL.glClear(GL.GL_COLOR_BUFFER_BIT | GL.GL_DEPTH_BUFFER_BIT)
        GL.glUseProgram(prog)
        GL.glUniformMatrix4fv(GL.glGetUniformLocation(prog, "mvp"), 1, True, matrix.astype(np.float32))
        GL.glUniform1i(GL.glGetUniformLocation(prog, "picking"), picking)
        GL.glDrawArrays(GL.GL_TRIANGLES, 0, len(data))

    t = time.perf_counter()
    draw(mvp(0))
    GL.glFinish()
    first = time.perf_counter() - t
    frames = 60
    t = time.perf_counter()
    for k in range(frames):
        draw(mvp(2 * k))
        GL.glFinish()
    per_frame = (time.perf_counter() - t) / frames

    matrix = mvp(0)
    target_index = next(i for i, m in enumerate(meshes) if m.kind == "IfcWall")
    clip = matrix @ np.append(meshes[target_index].vertices.mean(axis=0), 1.0)
    ndc = clip[:3] / clip[3]
    x, y = int((ndc[0] + 1) / 2 * W), int((ndc[1] + 1) / 2 * H)  # GL origin: bottom left
    timings = []
    for _ in range(2):
        t = time.perf_counter()
        draw(matrix, picking=1)
        pixel = GL.glReadPixels(x, y, 1, 1, GL.GL_RGBA, GL.GL_UNSIGNED_BYTE)
        timings.append(time.perf_counter() - t)
    r, g, b = pixel[0], pixel[1], pixel[2]
    index = (r | (g << 8) | (b << 16)) - 1
    hit = "the right wall" if index == target_index else (f"element {index}" if index >= 0 else "nothing")

    draw(matrix)
    fbo.toImage().save(out)
    fbo.release()
    print(
        f"{name}: {len(meshes)} meshes, {stats['triangles']} triangles; scene {build:.3f}s, "
        f"first frame {first:.3f}s, {per_frame * 1000:.1f} ms/frame, pick {timings[0] * 1000:.1f} ms "
        f"(again {timings[1] * 1000:.1f} ms) -> {hit}"
    )


if __name__ == "__main__":
    app = QGuiApplication(sys.argv[:1])
    fmt = QSurfaceFormat()
    fmt.setVersion(3, 3)
    fmt.setProfile(QSurfaceFormat.OpenGLContextProfile.CoreProfile)
    ctx = QOpenGLContext()
    ctx.setFormat(fmt)
    assert ctx.create(), "no OpenGL 3.3 context"
    surface = QOffscreenSurface()
    surface.setFormat(ctx.format())
    surface.create()
    ctx.makeCurrent(surface)
    print("OpenGL:", GL.glGetString(GL.GL_VERSION).decode(), "/", GL.glGetString(GL.GL_RENDERER).decode())
    out = sys.argv[1]
    run("house", house(), f"{out}/gl-house.png", ctx, surface)
    run("grid 15", grid(15), f"{out}/gl-grid.png", ctx, surface)
