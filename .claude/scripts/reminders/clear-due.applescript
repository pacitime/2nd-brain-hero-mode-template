-- Toglie la scadenza a una reminder attiva (drag nel Backlog).
-- macOS non permette sempre `set due date to missing value`: azzeriamo tutti i campi data,
-- ognuno in un try, poi verifichiamo che la data sia davvero sparita.
-- Uso: osascript clear-due.applescript "<NomeLista>" "<NomeReminder>"
on run argv
	set listName to item 1 of argv
	set remName to item 2 of argv
	tell application "Reminders"
		set matches to (reminders of list listName whose name is remName and completed is false)
		if matches is {} then return "ERR non trovato"
		set r to item 1 of matches
		try
			set remind me date of r to missing value
		end try
		try
			set allday due date of r to missing value
		end try
		try
			set due date of r to missing value
		end try
		if (due date of r is missing value) then
			return "OK " & remName
		else
			return "ERR data ancora presente"
		end if
	end tell
end run
