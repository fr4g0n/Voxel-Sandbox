from ursina import *
from ursina.prefabs.first_person_controller import FirstPersonController
import json

app = Ursina(title='Voxel Sandbox', borderless=False, vsync=False)

Sky()
pivot = Entity()
DirectionalLight(parent=pivot, y=2, z=3, shadows=True, rotation=(45, -45, 0))
AmbientLight(color=color.rgba(180, 180, 180, 255))

# --- stałe ---
CHUNK_SIZE  = 16
RENDER_DIST = 2
Y_MIN, Y_MAX = -2, 6
SAVE_FILE   = "world.json"

BLOCK_COLORS = {
    'grass': (0.22, 0.60, 0.22),
    'dirt':  (0.55, 0.35, 0.17),
    'stone': (0.52, 0.52, 0.52),
    'sand':  (0.85, 0.78, 0.50),
    'wood':  (0.65, 0.47, 0.28),
    'log':   (0.35, 0.22, 0.10),
    'leaf':  (0.18, 0.50, 0.12),
    'brick': (0.72, 0.36, 0.24),
}
BLOCK_COLOR_UI = {k: color.Color(*v, 1) for k, v in BLOCK_COLORS.items()}
block_types    = list(BLOCK_COLORS.keys())
selected_block = 0

world_data      = {}
collider_blocks = {}
chunk_meshes    = {}
loaded_chunks   = set()

flying  = False
FLY_SPD = 10

try:
    with open(SAVE_FILE) as f:
        world_data = json.load(f)
    print(f"[OK] Wczytano {SAVE_FILE}")
except (FileNotFoundError, json.JSONDecodeError) as e:
    print(f"[INFO] Nowy świat: {e}")


def shade(r, g, b, face):
    m = {'top': 1.15, 'bottom': 0.55, 'left': 0.80,
         'right': 0.80, 'front': 0.70, 'back': 0.70}[face]
    return (min(r * m, 1.0), min(g * m, 1.0), min(b * m, 1.0), 1.0)


def key3(x, y, z):
    return f"{int(x)},{int(y)},{int(z)}"


def chunk_of(x, z):
    return (int(x) // CHUNK_SIZE, int(z) // CHUNK_SIZE)


def ensure_column(x, z):
    x, z = int(x), int(z)
    if key3(x, 0, z) in world_data:
        return
    world_data[key3(x,  0, z)] = 'grass'
    world_data[key3(x, -1, z)] = 'dirt'
    world_data[key3(x, -2, z)] = 'stone'


# Oryginalne wierzchołki z pierwszej wersji — działały poprawnie geometrycznie.
# Każdy quad to 4 pkt, dwa trójkąty: (0,1,2) i (0,2,3).
FACES = [
    (( 0,  1,  0), [(-0.5, 0.5,-0.5),( 0.5, 0.5,-0.5),( 0.5, 0.5, 0.5),(-0.5, 0.5, 0.5)],  'top'),
    (( 0, -1,  0), [(-0.5,-0.5, 0.5),( 0.5,-0.5, 0.5),( 0.5,-0.5,-0.5),(-0.5,-0.5,-0.5)],  'bottom'),
    (( 1,  0,  0), [( 0.5,-0.5,-0.5),( 0.5, 0.5,-0.5),( 0.5, 0.5, 0.5),( 0.5,-0.5, 0.5)],  'right'),
    ((-1,  0,  0), [(-0.5,-0.5, 0.5),(-0.5, 0.5, 0.5),(-0.5, 0.5,-0.5),(-0.5,-0.5,-0.5)],  'left'),
    (( 0,  0,  1), [(-0.5,-0.5, 0.5),( 0.5,-0.5, 0.5),( 0.5, 0.5, 0.5),(-0.5, 0.5, 0.5)],  'front'),
    (( 0,  0, -1), [( 0.5,-0.5,-0.5),(-0.5,-0.5,-0.5),(-0.5, 0.5,-0.5),( 0.5, 0.5,-0.5)],  'back'),
]


def build_chunk(cx, cz):
    if (cx, cz) in chunk_meshes:
        destroy(chunk_meshes.pop((cx, cz)))

    x0, z0 = cx * CHUNK_SIZE, cz * CHUNK_SIZE
    for x in range(x0, x0 + CHUNK_SIZE):
        for z in range(z0, z0 + CHUNK_SIZE):
            ensure_column(x, z)

    verts, tris, norms, cols = [], [], [], []

    for x in range(x0, x0 + CHUNK_SIZE):
        for z in range(z0, z0 + CHUNK_SIZE):
            for y in range(Y_MIN, Y_MAX + 1):
                bname = world_data.get(key3(x, y, z))
                if not bname:
                    continue
                r, g, b = BLOCK_COLORS[bname]

                for (nx, ny, nz), quad, face_id in FACES:
                    if world_data.get(key3(x + nx, y + ny, z + nz)):
                        continue

                    fc   = shade(r, g, b, face_id)
                    base = len(verts)

                    for lx, ly, lz in quad:
                        verts.append((x + lx, y + ly, z + lz))
                        norms.append((nx, ny, nz))
                        cols.append(fc)

                    tris += [base, base+1, base+2, base, base+2, base+3]

    if not verts:
        return

    mesh = Mesh(
        vertices  = verts,
        triangles = tris,
        normals   = norms,
        colors    = cols,
        mode      = 'triangle',
    )
    ent = Entity(
        model       = mesh,
        color       = color.white,
        collider    = None,
        # double_sided=True żeby obie strony każdego trójkąta były widoczne —
        # eliminuje prześwitywanie przez "złą" stronę ściany
        double_sided = True,
    )
    # Wyłącz przezroczystość na tym entycie
    ent.setTransparency(0)
    chunk_meshes[(cx, cz)] = ent


def drop_chunk(cx, cz):
    if (cx, cz) in chunk_meshes:
        destroy(chunk_meshes.pop((cx, cz)))


def refresh_chunk(cx, cz):
    loaded_chunks.discard((cx, cz))
    build_chunk(cx, cz)
    loaded_chunks.add((cx, cz))


def update_colliders():
    px, py, pz = int(round(player.x)), int(round(player.y)), int(round(player.z))
    R = 5

    needed = set()
    for dx in range(-R, R+1):
        for dy in range(-4, R+2):
            for dz in range(-R, R+1):
                c = (px+dx, py+dy, pz+dz)
                if world_data.get(key3(*c)):
                    needed.add(c)

    for c in needed - set(collider_blocks):
        collider_blocks[c] = Entity(
            model='cube', color=color.clear,
            position=Vec3(*c), collider='box',
        )
    for c in set(collider_blocks) - needed:
        destroy(collider_blocks.pop(c))


def update_chunks():
    pcx, pcz = chunk_of(player.x, player.z)
    wanted = {(pcx+dx, pcz+dz)
              for dx in range(-RENDER_DIST, RENDER_DIST+1)
              for dz in range(-RENDER_DIST, RENDER_DIST+1)}

    for c in list(loaded_chunks - wanted):
        drop_chunk(*c)
        loaded_chunks.discard(c)

    for c in wanted - loaded_chunks:
        build_chunk(*c)
        loaded_chunks.add(c)


player          = FirstPersonController()
player.position = Vec3(CHUNK_SIZE // 2, 3, CHUNK_SIZE // 2)
player.speed    = 6
player.gravity  = 1.0
mouse.visible   = False
mouse.locked    = True

update_chunks()
update_colliders()


def set_flying(on):
    global flying
    flying = on
    if on:
        player.gravity = 0
        player.speed   = FLY_SPD
        fly_lbl.text   = '✈ Latanie'
    else:
        player.gravity = 1.0
        player.speed   = 6
        fly_lbl.text   = ''


hl = Entity(model='wireframe_cube', color=color.Color(1, 1, 1, 0.8),
            scale=1.02, enabled=False, collider=None, double_sided=True)

Entity(parent=camera.ui, model='quad', color=color.white, scale=(0.03, 0.003))
Entity(parent=camera.ui, model='quad', color=color.white, scale=(0.003, 0.03))

N, GAP, SZ = len(block_types), 0.08, 0.07
Entity(parent=camera.ui, model='quad',
       color=color.Color(0, 0, 0, 0.55),
       scale=(N * GAP + 0.02, SZ + 0.025), position=(0, -0.44))

slots, icons = [], []
for i, name in enumerate(block_types):
    ox = -GAP * (N-1) / 2 + i * GAP
    slots.append(Entity(parent=camera.ui, model='quad',
                        color=color.Color(0.3, 0.3, 0.3, 0.8),
                        scale=SZ, position=(ox, -0.44)))
    icons.append(Entity(parent=camera.ui, model='quad',
                        color=BLOCK_COLOR_UI[name],
                        scale=SZ * 0.55, position=(ox, -0.44)))
    Text(text=name, parent=camera.ui, origin=(0, 0),
         scale=0.45, position=(ox, -0.44 - SZ * 0.62),
         color=color.Color(0.85, 0.85, 0.85, 0.9))

Text(text="LPM: usuń  PPM: postaw  1-8/Scroll: blok  F: lot  F11: pełny ekran  P: zapisz",
     parent=camera.ui, origin=(0, 0), scale=0.6, position=(0, 0.46),
     color=color.Color(1, 1, 1, 0.6))

fly_lbl  = Text(text='', parent=camera.ui, origin=(1, 1),
                scale=0.8, position=(0.84, 0.48),
                color=color.Color(0.4, 1, 1, 0.9))
save_lbl = Text(text='', parent=camera.ui, origin=(0, 0),
                scale=1.1, position=(0, 0.38),
                color=color.Color(0.4, 1, 0.4, 1))
save_t = [0.0]


def refresh_hotbar():
    for i, s in enumerate(slots):
        if i == selected_block:
            s.color = color.Color(0.9, 0.75, 0.0, 0.95)
            s.scale = SZ * 1.18
        else:
            s.color = color.Color(0.3, 0.3, 0.3, 0.8)
            s.scale = SZ

refresh_hotbar()


def cast():
    ignore = [hl] + list(chunk_meshes.values())
    return raycast(camera.world_position, camera.forward,
                   distance=7, ignore=ignore)


def input(key):
    global selected_block

    for i in range(len(block_types)):
        if key == str(i + 1):
            selected_block = i
            refresh_hotbar()
            return

    if key == 'scroll up':
        selected_block = (selected_block - 1) % len(block_types)
        refresh_hotbar()
        return
    if key == 'scroll down':
        selected_block = (selected_block + 1) % len(block_types)
        refresh_hotbar()
        return

    if key == 'f':
        set_flying(not flying)
        return
    if key == 'f11':
        window.fullscreen = not window.fullscreen
        return
    if key == 'p':
        save_world()
        return

    if key not in ('left mouse down', 'right mouse down'):
        return

    hit = cast()
    if not hit.hit or not hit.entity:
        return

    bx = int(round(hit.entity.world_position.x))
    by = int(round(hit.entity.world_position.y))
    bz = int(round(hit.entity.world_position.z))

    if key == 'left mouse down':
        coord = (bx, by, bz)
        k = key3(*coord)
        if world_data.get(k):
            world_data[k] = None
            refresh_chunk(*chunk_of(bx, bz))
            if coord in collider_blocks:
                destroy(collider_blocks.pop(coord))

    else:
        nx = bx + int(round(hit.normal.x))
        ny = by + int(round(hit.normal.y))
        nz = bz + int(round(hit.normal.z))
        coord = (nx, ny, nz)
        k = key3(*coord)
        if not world_data.get(k):
            world_data[k] = block_types[selected_block]
            refresh_chunk(*chunk_of(nx, nz))
            collider_blocks[coord] = Entity(
                model='cube', color=color.clear,
                position=Vec3(*coord), collider='box',
            )


_t_chunk = 0.0
_t_coll  = 0.0


def update():
    global _t_chunk, _t_coll

    if flying:
        if held_keys['space']:
            player.y += FLY_SPD * time.dt
        if held_keys['left shift']:
            player.y -= FLY_SPD * time.dt

    _t_chunk += time.dt
    if _t_chunk >= 1.0:
        _t_chunk = 0
        update_chunks()

    _t_coll += time.dt
    if _t_coll >= 0.15:
        _t_coll = 0
        update_colliders()

    hit = cast()
    if hit.hit and hit.entity:
        hl.enabled  = True
        hl.position = hit.entity.world_position
    else:
        hl.enabled = False

    if save_t[0] > 0:
        save_t[0] -= time.dt
        if save_t[0] <= 0:
            save_lbl.text = ''


def save_world():
    try:
        with open(SAVE_FILE, 'w') as f:
            json.dump({k: v for k, v in world_data.items() if v}, f)
        save_lbl.text = '  Zapisano!'
        save_t[0] = 2.5
    except Exception as e:
        save_lbl.text = '  Błąd zapisu!'
        save_t[0] = 2.5
        print(f'[ERR] {e}')


app.run()