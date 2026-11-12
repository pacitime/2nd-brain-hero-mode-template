-- Crea una nuova reminder in una lista, con scadenza opzionale.
-- Uso: osascript create.applescript "<NomeLista>" "<NomeReminder>" [AAAA MM GG]
-- Output: "OK <nome>" oppure "ERR <messaggio>"
on run argv
	set listName to item 1 of argv
	set remName to item 2 of argv
	tell application "Reminders"
		try
			if (count of argv) ≥ 5 then
				set y to (item 3 of argv) as integer
				set m to (item 4 of argv) as integer
				set d to (item 5 of argv) as integer
				set dd to current date
				set hours of dd to 9
				set minutes of dd to 0
				set seconds of dd to 0
				set day of dd to 1
				set year of dd to y
				set month of dd to m
				set day of dd to d
				make new reminder at end of list listName with properties {name:remName, due date:dd}
			else
				make new reminder at end of list listName with properties {name:remName}
			end if
			return "OK " & remName
		on error errMsg
			return "ERR " & errMsg
		end try
	end tell
end run
