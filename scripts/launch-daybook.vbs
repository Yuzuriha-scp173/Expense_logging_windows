Set fso = CreateObject("Scripting.FileSystemObject")
Set shell = CreateObject("WScript.Shell")

scriptDir = fso.GetParentFolderName(WScript.ScriptFullName)
root = fso.GetParentFolderName(scriptDir)
pathFile = scriptDir & "\project-path.txt"

If fso.FileExists(pathFile) Then
  Set tf = fso.OpenTextFile(pathFile, 1)
  line = Trim(tf.ReadLine)
  tf.Close
  If Len(line) > 0 Then root = line
End If

If Not fso.FileExists(root & "\package.json") Then
  MsgBox "Daybook cannot find the project folder." & vbCrLf & vbCrLf & _
    "Open Command Prompt, cd into the folder you downloaded, then run:" & vbCrLf & vbCrLf & _
    "install.bat", vbExclamation, "Daybook"
  WScript.Quit 1
End If

electron = root & "\node_modules\electron\dist\electron.exe"
If Not fso.FileExists(electron) Then
  MsgBox "Daybook still needs a one-time setup." & vbCrLf & vbCrLf & _
    "Open Command Prompt, cd into:" & vbCrLf & vbCrLf & root & vbCrLf & vbCrLf & _
    "Then run:" & vbCrLf & vbCrLf & "install.bat", vbExclamation, "Daybook"
  WScript.Quit 1
End If

shell.Environment("PROCESS")("DAYBOOK_STANDALONE") = "1"
shell.CurrentDirectory = root
shell.Run """" & electron & """ """ & root & """", 0, False
