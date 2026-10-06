; NSIS may retain a same-named shortcut during an update. electron-builder's
; default Finish-page action launches $launchLink, which prefers that shortcut
; over the installed executable. If the preserved link has an obsolete target,
; Windows shows "Problem with Shortcut" instead of reopening Flo.
; Repoint package-owned shortcuts at this install and launch Flo.exe directly.
!macro customInstall
  !ifndef DO_NOT_CREATE_START_MENU_SHORTCUT
    Delete "$newStartMenuLink"
    CreateShortCut "$newStartMenuLink" "$appExe" "" "$appExe" 0 "" "" "${APP_DESCRIPTION}"
  !endif

  !ifndef DO_NOT_CREATE_DESKTOP_SHORTCUT
    ${ifNot} ${isNoDesktopShortcut}
      Delete "$newDesktopLink"
      CreateShortCut "$newDesktopLink" "$appExe" "" "$appExe" 0 "" "" "${APP_DESCRIPTION}"
    ${endIf}
  !endif

  StrCpy $launchLink "$appExe"
!macroend
