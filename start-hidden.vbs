Option Explicit

Dim shell, files, root, batchPath, logPath, iconPath, desktopPath, shortcutPath
Dim shortcut, command, request, attempt, quote

If WScript.Arguments.Named.Exists("validate") Then
    WScript.Echo "Pangdun launcher syntax OK"
    WScript.Quit 0
End If

Set shell = CreateObject("WScript.Shell")
Set files = CreateObject("Scripting.FileSystemObject")
root = files.GetParentFolderName(WScript.ScriptFullName)
batchPath = files.BuildPath(root, "start.bat")
logPath = files.BuildPath(root, "backend\data\crm-start.log")
iconPath = files.BuildPath(root, "frontend\public\favicon.ico")
quote = Chr(34)

desktopPath = shell.SpecialFolders("Desktop")
shortcutPath = files.BuildPath(desktopPath, "Pangdun CRM.lnk")
Set shortcut = shell.CreateShortcut(shortcutPath)
shortcut.TargetPath = shell.ExpandEnvironmentStrings("%SystemRoot%\System32\wscript.exe")
shortcut.Arguments = quote & WScript.ScriptFullName & quote
shortcut.WorkingDirectory = root
shortcut.Description = "Pangdun KOL CRM"
shortcut.IconLocation = iconPath & ",0"
shortcut.Save

If Not files.FileExists(files.BuildPath(root, "backend\data\kol_crm.db")) Then
    MsgBox "First-time setup needs a visible installer window. Daily launches will run quietly in the background.", 64, "Pangdun CRM"
    shell.Run quote & batchPath & quote & " --foreground", 1, False
    WScript.Quit 0
End If

If IsHealthy() Then
    shell.Run "http://127.0.0.1:8000", 1, False
    WScript.Quit 0
End If

command = "cmd.exe /d /c " & quote & quote & batchPath & quote & " --worker > " & quote & logPath & quote & " 2>&1" & quote
shell.Run command, 0, False

For attempt = 1 To 1800
    WScript.Sleep 500
    If IsHealthy() Then
        shell.Run "http://127.0.0.1:8000", 1, False
        WScript.Quit 0
    End If
Next

MsgBox "Pangdun CRM did not start. Please send this log file to the administrator:" & vbCrLf & logPath, 48, "Pangdun CRM"
WScript.Quit 1

Function IsHealthy()
    On Error Resume Next
    Set request = CreateObject("MSXML2.XMLHTTP.6.0")
    request.Open "GET", "http://127.0.0.1:8000/api/health", False
    request.setRequestHeader "Cache-Control", "no-cache"
    request.Send
    IsHealthy = (Err.Number = 0 And request.Status = 200)
    Err.Clear
    On Error GoTo 0
End Function
