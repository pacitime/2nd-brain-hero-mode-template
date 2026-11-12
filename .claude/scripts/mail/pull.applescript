-- Legge le email RECENTI della inbox di un account di Apple Mail. SOLA LETTURA:
-- non invia, non risponde, non marca come letto, non sposta nulla.
-- Uso: osascript pull.applescript "<NomeAccount>" [giorni] [max]
--   giorni  = quanto indietro guardare (default 1)
--   max     = tetto di messaggi restituiti (default 25)
-- Output: una riga per email, campi separati da TAB →
--   AAAA-MM-GG HH:MM <TAB> letta|NON-letta <TAB> mittente <TAB> oggetto <TAB> anteprima <TAB> message-id
-- L'anteprima e' troncata a 300 char e appiattita su una riga: il corpo intero si prende
-- con read.applescript passando il message-id (l'ultimo campo).
-- Fetch in BLOCCO delle proprieta' (una chiamata per campo invece di una per messaggio):
-- iterare messaggio-per-messaggio scatena troppi Apple Event e Mail si impianta.
on run argv
	set acctName to item 1 of argv
	if (count of argv) > 1 then
		set daysBack to (item 2 of argv) as integer
	else
		set daysBack to 1
	end if
	if (count of argv) > 2 then
		set maxMsgs to (item 3 of argv) as integer
	else
		set maxMsgs to 25
	end if
	-- l'anteprima del corpo costa (una fetch per messaggio, spesso di rete): opt-in
	set wantPreview to ((count of argv) > 3 and (item 4 of argv) is "prev")

	set cutoff to (current date) - (daysBack * days)

	tell application "Mail"
		set acct to first account whose name is acctName
		try
			set mbx to first mailbox of acct whose name is "INBOX"
		on error
			set mbx to first mailbox of acct
		end try
		-- una query per campo, ognuna col suo filtro: applicare 'date received of' a una
		-- LISTA di riferimenti gia' raccolta fallisce (-1728), va rifatta la whose-clause.
		set dts to date received of (messages of mbx whose date received > cutoff)
		set rds to read status of (messages of mbx whose date received > cutoff)
		set snds to sender of (messages of mbx whose date received > cutoff)
		set sbjs to subject of (messages of mbx whose date received > cutoff)
		set ids to message id of (messages of mbx whose date received > cutoff)
		set msgs to (messages of mbx whose date received > cutoff)
	end tell

	set n to count of dts
	if n > maxMsgs then set n to maxMsgs

	set out to ""
	repeat with i from 1 to n
		set dt to item i of dts
		set stampa to (year of dt as string) & "-" & my pad(month of dt) & "-" & my pad(day of dt) & " " & my pad(hours of dt) & ":" & my pad(minutes of dt)
		if (item i of rds) then
			set letto to "letta"
		else
			set letto to "NON-letta"
		end if
		set mid to item i of ids
		set prev to ""
		if wantPreview then
			-- si indicizza la lista di riferimenti gia' in mano: cercare col message-id
			-- (whose message id is ...) farebbe una scansione del mailbox per OGNI messaggio.
			try
				tell application "Mail" to set bdy to content of (item i of msgs)
				if (count of bdy) > 300 then set bdy to (text 1 thru 300 of bdy) & "…"
				set prev to my flatten(bdy)
			end try
		end if
		set out to out & stampa & tab & letto & tab & my flatten(item i of snds) & tab & my flatten(item i of sbjs) & tab & prev & tab & mid & linefeed
	end repeat
	return out
end run

on pad(n)
	set n to n as integer
	if n < 10 then return "0" & (n as string)
	return n as string
end pad

-- appiattisce su una riga: TAB/linefeed/return dentro un campo romperebbero il formato
on flatten(t)
	set t to t as string
	set old to AppleScript's text item delimiters
	repeat with ch in {tab, linefeed, (ASCII character 13)}
		set AppleScript's text item delimiters to (contents of ch)
		set parts to text items of t
		set AppleScript's text item delimiters to " "
		set t to parts as string
	end repeat
	set AppleScript's text item delimiters to old
	return t
end flatten
