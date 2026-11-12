-- Legge i promemoria NON completati di una lista, NELL'ORDINE dell'app Apple.
-- Uso: osascript pull.applescript "<NomeLista>"
-- Output: una riga per promemoria → "nome<TAB>AAAA-MM-GG" (data vuota se assente).
-- Fetch in BLOCCO (name/due date di tutta la lista in 2 chiamate): iterare reminder-per-reminder
-- scatena troppi Apple Event e Reminders si impianta.
on run argv
	set listName to item 1 of argv
	tell application "Reminders"
		set nms to name of (every reminder in list listName whose completed is false)
		set dds to due date of (every reminder in list listName whose completed is false)
	end tell
	set out to ""
	repeat with i from 1 to (count of nms)
		set nm to item i of nms
		set dd to item i of dds
		if dd is missing value then
			set ds to ""
		else
			set ds to (year of dd as string) & "-" & my pad(month of dd) & "-" & my pad(day of dd)
		end if
		set out to out & nm & tab & ds & linefeed
	end repeat
	return out
end run

on pad(n)
	set n to n as integer
	if n < 10 then
		return "0" & (n as string)
	end if
	return n as string
end pad
