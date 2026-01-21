# Kodi Settings

Reference for Kodi settings that can be manipulated via skin utilities.

[← Back to Index](index.md)

See [Skin Utilities](skin-utilities.md) for usage instructions.

---

## Table of Contents

- [Video Player](#video-player)
- [Music Player](#music-player)
- [Pictures](#pictures)
- [Language & Subtitles](#language--subtitles)
- [Library](#library)
- [File Lists](#file-lists)
- [Display](#display)
- [Audio](#audio)
- [Skin](#skin)
- [Screensaver](#screensaver)
- [Setting Types](#setting-types)
- [Limitations](#limitations)

---

## Video Player

| Setting | Type | Description |
| ------- | ---- | ----------- |
| `videoplayer.autoplaynextitem` | list | Auto play next item behavior |
| `videoplayer.seeksteps` | list | Seek step increments |
| `videoplayer.seekdelay` | integer | Seek delay in milliseconds |
| `videoplayer.adjustrefreshrate` | integer | Adjust refresh rate on playback |
| `videoplayer.usedisplayasclock` | boolean | Use display as clock |
| `videoplayer.errorinaspect` | integer | Error in aspect ratio |
| `videoplayer.stretch43` | integer | Stretch 4:3 content |
| `videoplayer.rendermethod` | integer | Render method |
| `videoplayer.hqscalers` | integer | High quality scalers |
| `videoplayer.usesuperresolution` | boolean | Use super resolution |
| `videoplayer.stereoscopicplaybackmode` | integer | Stereoscopic playback mode |
| `videoplayer.quitstereomodeonstop` | boolean | Quit stereo mode on stop |
| `videoplayer.teletextenabled` | boolean | Teletext enabled |
| `videoplayer.teletextscale` | boolean | Teletext scale |
| `videoplayer.preferdefaultflag` | boolean | Prefer default audio flag |

---

## Music Player

| Setting | Type | Description |
| ------- | ---- | ----------- |
| `musicplayer.autoplaynextitem` | boolean | Auto play next item |
| `musicplayer.queuebydefault` | boolean | Queue songs by default |
| `musicplayer.seeksteps` | list | Seek step increments |
| `musicplayer.seekdelay` | integer | Seek delay in milliseconds |
| `musicplayer.crossfade` | integer | Crossfade duration |
| `musicplayer.crossfadealbumtracks` | boolean | Crossfade album tracks |
| `musicplayer.visualisation` | addon | Visualization addon |
| `musicplayer.replaygaintype` | integer | Replay gain type |
| `musicplayer.replaygainpreamp` | integer | Replay gain preamp |
| `musicplayer.replaygainnogainpreamp` | integer | No gain preamp |
| `musicplayer.replaygainavoidclipping` | boolean | Avoid clipping |

---

## Pictures

| Setting | Type | Description |
| ------- | ---- | ----------- |
| `pictures.usetags` | boolean | Use picture tags |
| `pictures.generatethumbs` | boolean | Generate thumbnails |
| `pictures.showvideos` | boolean | Show videos in pictures |
| `pictures.displayresolution` | integer | Display resolution |
| `slideshow.staytime` | integer | Slideshow stay time (seconds) |
| `slideshow.displayeffects` | boolean | Display slideshow effects |
| `slideshow.shuffle` | boolean | Shuffle slideshow |
| `slideshow.highqualitydownscaling` | boolean | High quality downscaling |

---

## Language & Subtitles

**Language:**

| Setting | Type | Description |
| ------- | ---- | ----------- |
| `locale.audiolanguage` | string | Preferred audio language |
| `locale.subtitlelanguage` | string | Preferred subtitle language |
| `accessibility.audiovisual` | boolean | Audio for visually impaired |
| `accessibility.audiohearing` | boolean | Audio for hearing impaired |
| `accessibility.subhearing` | boolean | Subtitles for hearing impaired |

**Subtitle Appearance:**

| Setting | Type | Description |
| ------- | ---- | ----------- |
| `subtitles.align` | integer | Subtitle alignment |
| `subtitles.fontname` | string | Font name |
| `subtitles.fontsize` | integer | Font size |
| `subtitles.style` | integer | Style (bold, italic) |
| `subtitles.colorpick` | string | Text color |
| `subtitles.opacity` | integer | Text opacity |
| `subtitles.bordersize` | integer | Border size |
| `subtitles.bordercolorpick` | string | Border color |
| `subtitles.blur` | integer | Blur amount |
| `subtitles.linespacing` | integer | Line spacing |
| `subtitles.backgroundtype` | integer | Background type |
| `subtitles.bgcolorpick` | string | Background color |
| `subtitles.bgopacity` | integer | Background opacity |
| `subtitles.shadowcolor` | string | Shadow color |
| `subtitles.shadowopacity` | integer | Shadow opacity |
| `subtitles.shadowsize` | integer | Shadow size |
| `subtitles.marginvertical` | number | Vertical margin |
| `subtitles.overridefonts` | boolean | Override fonts |
| `subtitles.stereoscopicdepth` | integer | Stereoscopic depth |

**Subtitle Downloads:**

| Setting | Type | Description |
| ------- | ---- | ----------- |
| `subtitles.languages` | list | Subtitle languages |
| `subtitles.storagemode` | integer | Storage mode |
| `subtitles.custompath` | path | Custom storage path |
| `subtitles.pauseonsearch` | boolean | Pause on search |
| `subtitles.downloadfirst` | boolean | Download first match |
| `subtitles.tv` | addon | TV subtitle service |
| `subtitles.movie` | addon | Movie subtitle service |

---

## Library

**Video Library:**

| Setting | Type | Description |
| ------- | ---- | ----------- |
| `videolibrary.updateonstartup` | boolean | Update on startup |
| `videolibrary.backgroundupdate` | boolean | Background update |
| `videolibrary.ignorevideoversions` | boolean | Ignore video versions |
| `videolibrary.ignorevideoextras` | boolean | Ignore video extras |

**Music Library:**

| Setting | Type | Description |
| ------- | ---- | ----------- |
| `musiclibrary.updateonstartup` | boolean | Update on startup |
| `musiclibrary.backgroundupdate` | boolean | Background update |
| `musiclibrary.exportfiletype` | integer | Export file type |
| `musiclibrary.exportfolder` | string | Export folder |
| `musiclibrary.exportitems` | integer | Export items |
| `musiclibrary.exportunscraped` | boolean | Export unscraped |
| `musiclibrary.exportoverwrite` | boolean | Export overwrite |
| `musiclibrary.exportartwork` | boolean | Export artwork |
| `musiclibrary.exportskipnfo` | boolean | Skip NFO export |

---

## File Lists

| Setting | Type | Description |
| ------- | ---- | ----------- |
| `filelists.showparentdiritems` | boolean | Show parent directory items (..) |
| `filelists.ignorethewhensorting` | boolean | Ignore "the" when sorting |
| `filelists.showextensions` | boolean | Show file extensions |
| `filelists.showaddsourcebuttons` | boolean | Show add source buttons |
| `filelists.showhidden` | boolean | Show hidden files |
| `filelists.allowfiledeletion` | boolean | Allow file deletion |
| `filelists.confirmfiledeletion` | boolean | Confirm file deletion |

---

## Display

| Setting | Type | Description |
| ------- | ---- | ----------- |
| `videoscreen.monitor` | string | Monitor selection |
| `videoscreen.screen` | integer | Screen number |
| `videoscreen.resolution` | integer | Resolution |
| `videoscreen.screenmode` | string | Screen mode |
| `videoscreen.fakefullscreen` | boolean | Fake fullscreen |
| `videoscreen.blankdisplays` | boolean | Blank other displays |
| `videoscreen.delayrefreshchange` | integer | Refresh change delay |
| `videoscreen.10bitsurfaces` | integer | 10-bit surfaces |
| `videoscreen.dither` | boolean | Dithering |
| `videoscreen.ditherdepth` | integer | Dither depth |

**Color Management:**

| Setting | Type | Description |
| ------- | ---- | ----------- |
| `videoscreen.cmsenabled` | boolean | Color management enabled |
| `videoscreen.cmsmode` | integer | Color management mode |
| `videoscreen.cms3dlut` | string | 3D LUT file |
| `videoscreen.displayprofile` | string | Display profile |
| `videoscreen.cmswhitepoint` | integer | White point |

---

## Audio

**Audio Output:**

| Setting | Type | Description |
| ------- | ---- | ----------- |
| `audiooutput.audiodevice` | string | Audio device |
| `audiooutput.channels` | integer | Channel count |
| `audiooutput.config` | integer | Audio configuration |
| `audiooutput.volumesteps` | integer | Volume steps |
| `audiooutput.maintainoriginalvolume` | boolean | Maintain original volume |
| `audiooutput.stereoupmix` | boolean | Stereo upmix |
| `audiooutput.processquality` | integer | Processing quality |
| `audiooutput.samplerate` | integer | Sample rate |
| `audiooutput.streamsilence` | integer | Stream silence |
| `audiooutput.streamnoise` | boolean | Stream noise |

**Audio Mixing:**

| Setting | Type | Description |
| ------- | ---- | ----------- |
| `audiooutput.mixsublevel` | integer | Mix subtitle level |
| `audiooutput.guisoundmode` | integer | GUI sound mode |
| `audiooutput.guisoundvolume` | integer | GUI sound volume |
| `lookandfeel.soundskin` | addon | Sound skin |

---

## Skin

| Setting | Type | Description |
| ------- | ---- | ----------- |
| `lookandfeel.skin` | addon | Active skin |
| `lookandfeel.skintheme` | string | Skin theme |
| `lookandfeel.skincolors` | string | Skin colors |
| `lookandfeel.font` | string | Skin font |
| `lookandfeel.skinzoom` | integer | Skin zoom level |
| `lookandfeel.stereostrength` | integer | Stereo strength |
| `lookandfeel.enablerssfeeds` | boolean | Enable RSS feeds |
| `lookandfeel.rssedit` | string | RSS feed editor |

---

## Screensaver

| Setting | Type | Description |
| ------- | ---- | ----------- |
| `screensaver.mode` | addon | Screensaver addon |
| `screensaver.time` | integer | Screensaver timeout (minutes) |
| `screensaver.disableforaudio` | boolean | Disable for audio |
| `screensaver.usedimonpause` | boolean | Dim on pause |

---

## Setting Types

| Type | Description | Can Toggle | Can Get | Can Set | Can Reset |
| ---- | ----------- | ---------- | ------- | ------- | --------- |
| `boolean` | True/False value | Yes | Yes | Yes | Yes |
| `integer` | Numeric value | No | Yes | Yes | Yes |
| `number` | Decimal number | No | Yes | Yes | Yes |
| `string` | Text value | No | Yes | Yes | Yes |
| `list` | List/array value | No | Yes | Yes | Yes |
| `addon` | Addon selection | No | Yes | Yes | Yes |
| `path` | File/folder path | No | Yes | Yes | Yes |

---

## Limitations

**Based on Kodi source code analysis:**

1. **Visibility Requirement:**
   - Settings must have their visibility set to true
   - Hidden settings cannot be accessed via JSON-RPC

2. **Unsupported Types:**
   - `action` type settings cannot be get/set/reset (they trigger actions, not store values)
   - `unknown` type settings are not supported

3. **Toggle Limitation:**
   - Only `boolean` type settings can be toggled
   - Attempting to toggle non-boolean settings will fail silently

4. **Type Validation:**
   - `SetSettingValue` validates value type matches setting type
   - Passing wrong type (e.g., string to integer setting) returns error

**Source:** `xbmc/interfaces/json-rpc/SettingsOperations.cpp`
