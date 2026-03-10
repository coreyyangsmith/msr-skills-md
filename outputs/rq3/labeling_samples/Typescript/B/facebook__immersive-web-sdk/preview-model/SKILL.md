---
name: preview-model
description: Preview a 3D model from the Kenney Prototype Kit in the VR scene. Use when the user wants to see what a model looks like, test a model in the scene, or compare texture variations.
argument-hint: [model-name] [texture-variation?]
allowed-tools: Read, Edit, Bash, Write
---

# Preview Kenney Model in VR Scene

Preview models from the Kenney Prototype Kit by looking them up in the catalog, adding them to the scene, and taking IWER screenshots to verify.

## Arguments

- `$0` - Model name (e.g., `figurine`, `door-rotate`, `wall-corner`)
- `$1` - Texture variation: `a`, `b`, or `c` (optional, defaults to `a`)

## Workflow

### Step 1: Look Up Model in Catalog

First, search the catalog to find the model and understand what it looks like:

```
Catalog location: public/kenney_prototype-kit/catalog/
```

1. Read `catalog/README.md` to find which category the model is in
2. Read the specific category file to get the model description
3. Confirm the GLB filename exists

### Step 2: Copy Model and Texture to Public Folder

```bash
# Create kenney folder structure
mkdir -p public/kenney/Textures

# Copy the GLB file
cp "kenney_prototype-kit/Models/GLB format/[model-name].glb" public/kenney/

# Copy the texture variation as colormap.png
# Use variation-a.png, variation-b.png, or variation-c.png
cp "kenney_prototype-kit/Models/Textures/variation-[a|b|c].png" public/kenney/Textures/colormap.png
```

### Step 3: Add Model to Scene

Edit `src/index.ts` to add the model:

1. Add to asset manifest:

```typescript
kenneyPreview: {
  url: "/kenney/[model-name].glb",
  type: AssetType.GLTF,
  priority: "critical",
},
```

2. Add to scene after world creation:

```typescript
// Preview Kenney model
const { scene: previewMesh } = AssetManager.getGLTF('kenneyPreview')!;
previewMesh.position.set(0, 0.85, -1.5); // On desk, center
previewMesh.scale.setScalar(0.5); // Adjust as needed
world
  .createTransformEntity(previewMesh)
  .addComponent(Interactable)
  .addComponent(DistanceGrabbable, {
    movementMode: MovementMode.MoveFromTarget,
  });
```

### Step 4: Verify with IWER Screenshots

1. Check IWER connection: `mcp__iwsdk-dev-mcp__xr_get_session_status`
2. Reload page: `mcp__iwsdk-dev-mcp__browser_reload_page`
3. Wait for reload: `sleep 3`
4. Accept XR session: `mcp__iwsdk-dev-mcp__xr_accept_session`
5. Position headset to look at model:

```
mcp__iwsdk-dev-mcp__xr_look_at({
  device: "headset",
  target: { x: 0, y: 0.85, z: -1.5 },
  moveToDistance: 0.8
})
```

6. Take screenshot: `mcp__iwsdk-dev-mcp__browser_screenshot`

### Step 5: Report Results

Summarize:

- Model name and category
- Catalog description
- Texture variation used
- Screenshot showing the model in scene
- Any sizing/positioning recommendations

## Texture Variations

| Variation | File            | Color Scheme                               |
| --------- | --------------- | ------------------------------------------ |
| a         | variation-a.png | Purple/lavender base, orange/coral accents |
| b         | variation-b.png | Alternative color scheme                   |
| c         | variation-c.png | Alternative color scheme                   |

## Example Usage

```
/preview-model figurine
/preview-model door-rotate b
/preview-model wall-corner c
```

## Positioning Guide

Default position `(0, 0.85, -1.5)` places the model on the desk. Adjust based on model type:

| Model Type                   | Position        | Scale | Notes                   |
| ---------------------------- | --------------- | ----- | ----------------------- |
| Small props (coins, buttons) | (0, 0.9, -1.5)  | 1.0   | On desk surface         |
| Figurines, shapes            | (0, 0.85, -1.5) | 0.5   | On desk, half scale     |
| Walls, floors                | (0, 0, -3)      | 1.0   | On ground, further away |
| Doors                        | (0, 0, -2.5)    | 1.0   | On ground, room scale   |
| Vehicles                     | (2, 0, -3)      | 1.0   | On ground, to the side  |

## Cleanup

After previewing, remember to:

1. Remove or comment out the preview code from `src/index.ts`
2. Delete files from `public/kenney/` if not needed
3. Or keep them if you want to use the model permanently

## File Locations Reference

```
kenney_prototype-kit/
├── catalog/                    # Model descriptions
│   ├── README.md              # Master index
│   └── [category].md          # Category catalogs
├── Models/
│   ├── GLB format/            # 3D model files
│   │   └── [model].glb
│   └── Textures/              # Shared textures
│       ├── variation-a.png
│       ├── variation-b.png
│       └── variation-c.png
└── Previews/                  # 2D preview images
    └── [model].png
```
