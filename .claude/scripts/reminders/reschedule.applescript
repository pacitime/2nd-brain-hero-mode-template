-- Imposta/cambia la scadenza di una reminder attiva (data → ore 09:00).
-- Uso: osascript reschedule.applescript "<NomeLista>" "<NomeReminder>" AAAA MM GG
-- Output: "OK <nome>" oppure "ERR <messaggio>"
on run argv
	set listName to item 1 of argv
	set remName to item 2 of argv
	set y to (item 3 of argv) as integer
	set mo to (item 4 of argv) as integer
	set dy to (item 5 of argv) as integer
	tell application "Reminders"
		try
			set r to (first reminder of list listName whose name is remName and completed is false)
			set theDate to (current date)
			set day of theDate to 1
			set year of theDate to y
			set month of theDate to mo
			set day of theDate to dy
			set hours of theDate to 9
			set minutes of theDate to 0
			set seconds of theDate to 0
			set due date of r to theDate
			return "OK " & remName
		on error errMsg
			return "ERR " & errMsg
		end try
	end tell
end run
