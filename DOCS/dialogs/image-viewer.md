# Image Viewer Dialog

A full-screen image viewer for any plugin URL that returns image items. Left/right navigates, back/Esc closes.

[← Back to Index](../index.md)

---

## Launch

```xml
<!-- From the actor info dialog's Images panel -->
<onclick>RunScript(script.skin.info.service,action=dialog_image_viewer,
  images_path=$INFO[Window.Property(container.images.path)],
  selected_index=$INFO[Container(1506).CurrentItem])</onclick>

<!-- From any container whose content is an image directory -->
<onclick>RunScript(script.skin.info.service,action=dialog_image_viewer,
  images_path=$INFO[Window.Property(MyImagesPath)],
  selected_index=$INFO[Container.CurrentItem])</onclick>
```

## Parameters

| Parameter | Required | Description |
|-----------|----------|-------------|
| `images_path` | Yes | Plugin URL returning a directory of image ListItems. Any plugin that returns items with art works (e.g. `?action=person_info&info_type=images&person_id=N`). |
| `selected_index` | No | 1-based position to focus on open. Pass `$INFO[Container.CurrentItem]` directly — the dialog converts to 0-based internally. Default `1`. |
| `set_home_props` | No | Default `false`. |

## Window Properties

Set on the dialog window while it's open.

| Property | Description |
|----------|-------------|
| `container.viewer.path` | The image plugin URL currently being shown |
