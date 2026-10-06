; NSIS may retain a same-named shortcut during an update. electron-builder's
; default Finish-page action launches $launchLink through ShellExecute, so a
; stale shortcut target can produce "Problem with Shortcut" after a successful
; install. Keep shortcut repair, but own the Finish-page action and resolve the
; executable from the final $INSTDIR only after file replacement has finished.
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

; electron-builder calls customFinishPage instead of defining its StartApp
; function when this macro exists. This prevents an old retained shortcut or
; the pre-update launchLink value from participating in automatic relaunch.
!macro customFinishPage
  !ifndef HIDE_RUN_AFTER_FINISH
    Function FloRunInstalledExe
      ${if} ${isUpdated}
        StrCpy $1 "--updated"
      ${else}
        StrCpy $1 ""
      ${endif}

      StrCpy $2 0
    flo_wait_for_installed_exe:
      IfFileExists "$INSTDIR\${APP_EXECUTABLE_FILENAME}" flo_launch_installed_exe 0
      IntOp $2 $2 + 1
      ${if} $2 < 20
        ; Poll the specific final install target (max 5 seconds) in case the
        ; updater/NSIS replacement is still completing an in-use-file rename.
        Sleep 250
        Goto flo_wait_for_installed_exe
      ${endif}
      Return

    flo_launch_installed_exe:
      ${StdUtils.ExecShellAsUser} $0 "$INSTDIR\${APP_EXECUTABLE_FILENAME}" "open" "$1"
    FunctionEnd

    !define MUI_FINISHPAGE_RUN
    !define MUI_FINISHPAGE_RUN_FUNCTION "FloRunInstalledExe"
  !endif
  !insertmacro MUI_PAGE_FINISH
!macroend
