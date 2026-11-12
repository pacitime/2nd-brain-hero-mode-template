-- Legge le CALL/eventi imminenti (finestra oggi..+N giorni) da Apple Calendar.
-- Uso: osascript pull.applescript [giorni] ["<NomeCalendario>" ...]   (default 7 giorni)
--   I nomi dei calendari non stanno qui: chi chiama li legge da `.claude/config/brain.json`
--   (campo `calendars`, con brain_config.calendars()) e li passa dopo i giorni.
--   Senza nomi si leggono TUTTI i calendari.
-- Output: una riga per evento → "titolo<TAB>AAAA-MM-GG<TAB>HH:MM(inizio)<TAB>HH:MM(fine)<TAB>calendario"
-- Fetch in BLOCCO per calendario (summary/start/end in 3 chiamate): iterare evento-per-evento
-- scatena troppi Apple Event e Calendar si impianta (stessa lezione dei Promemoria).
-- Sola lettura: non crea, non modifica, non cancella nulla.
on run argv
	set winDays to 7
	if (count of argv) ≥ 1 then set winDays to (item 1 of argv) as integer
	set calNames to {}
	if (count of argv) ≥ 2 then set calNames to items 2 thru -1 of argv
	set startWin to (current date)
	set hours of startWin to 0
	set minutes of startWin to 0
	set seconds of startWin to 0
	set endWin to startWin + (winDays * days)
	set out to ""
	set seen to {}
	tell application "Calendar"
		if calNames is {} then set calNames to name of every calendar
		repeat with cn in calNames
			set cnText to cn as string
			-- due calendari con lo stesso nome: si legge il primo, una volta sola
			if seen does not contain cnText then
				set end of seen to cnText
				try
					set theCal to first calendar whose name is cnText
					set sums to summary of (every event of theCal whose start date ≥ startWin and start date ≤ endWin)
					set sts to start date of (every event of theCal whose start date ≥ startWin and start date ≤ endWin)
					set ens to end date of (every event of theCal whose start date ≥ startWin and start date ≤ endWin)
					repeat with i from 1 to (count of sums)
						set s to item i of sums
						set d to item i of sts
						set e to item i of ens
						set ds to (year of d as string) & "-" & my pad(month of d) & "-" & my pad(day of d)
						set t1 to my pad(hours of d) & ":" & my pad(minutes of d)
						set t2 to my pad(hours of e) & ":" & my pad(minutes of e)
						set out to out & s & tab & ds & tab & t1 & tab & t2 & tab & cnText & linefeed
					end repeat
				end try
			end if
		end repeat
	end tell
	return out
end run

on pad(n)
	set n to n as integer
	if n < 10 then
		return "0" & (n as string)
	end if
	return n as string
end pad
