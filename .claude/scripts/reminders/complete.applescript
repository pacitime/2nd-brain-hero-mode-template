-- Marca COMPLETATA una reminder attiva dato lista + nome (write-back per-nome).
-- Uso: osascript complete.applescript "<NomeLista>" "<NomeReminder>"
-- Output: "OK <nome>" oppure "ERR <messaggio>"
on run argv
	set listName to item 1 of argv
	set remName to item 2 of argv
	tell application "Reminders"
		try
			set r to (first reminder of list listName whose name is remName and completed is false)
			set completed of r to true
			return "OK " & remName
		on error errMsg
			return "ERR " & errMsg
		end try
	end tell
end run
