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

<!-- From a TMDB Posters list, in any dialog -->
<onclick>RunScript(script.skin.info.service,action=dialog_image_viewer,
  images_path=$INFO[ListItem.Property(images_path)],
  selected_index=$INFO[ListItem.CurrentItem])</onclick>

<!-- From any container whose content is an image directory -->
<onclick>RunScript(script.skin.info.service,action=dialog_image_viewer,
  images_path=$INFO[Window.Property(MyImagesPath)],
  selected_index=$INFO[Container.CurrentItem])</onclick>
```

## Parameters

| Parameter | Required | Description |
|-----------|----------|-------------|
| `images_path` | Yes | Plugin URL returning a directory of image ListItems. Any plugin that returns items with art works (e.g. `?action=person_info&info_type=images&person_id=N`). |
| `selected_index` | No | 1-based position to focus on open. Pass `$INFO[Container.CurrentItem]` directly. Default `1`. |

## Window Properties

Set on the dialog window while it's open.

| Property | Description |
|----------|-------------|
| `container.viewer.path` | The image plugin URL currently being shown |
| `artwork_view` | `true` when an artwork picker opened the viewer on one image; empty otherwise |

## Artwork Pickers

Info in an artwork picker opens the focused image in this viewer, one image at a time. Info, the
context menu, Back or Esc closes it. Its one item also carries `ListItem.Property(Source)`, the
provider (`TMDB` or `fanart.tv`), so a skin can show that in place of the image count:

```xml
<visible>!String.IsEmpty(Window.Property(artwork_view))</visible>
<label>$INFO[Container(1520).ListItem.Property(Source)]</label>
```
