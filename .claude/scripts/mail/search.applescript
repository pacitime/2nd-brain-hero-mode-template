-- Cerca nei mailbox di un account di Apple Mail per MITTENTE o OGGETTO. SOLA LETTURA:
-- non invia, non risponde, non marca come letto, non sposta nulla.
-- Uso: osascript search.applescript "<NomeAccount>" "<termine1>" ["<termine2>" ...]
-- Ogni termine viene cercato sia nell'oggetto sia nel mittente (match case-insensitive,
-- sottostringa). I termini sono in OR fra loro.
-- Output: una riga per email, campi separati da TAB →
--   mailbox <TAB> data <TAB> mittente <TAB> oggetto <TAB> message-id
-- Il corpo intero si prende con read.applescript passando il message-id (l'ultimo campo).
on run argv
	set acctName to item 1 of argv
	set terms to rest of argv
	set out to ""
	tell application "Mail"
		set acct to first account whose name is acctName
		repeat with mbx in (every mailbox of acct)
			repeat with t in terms
				try
					set hits to (messages of mbx whose (subject contains t or sender contains t))
					repeat with m in hits
						set dt to date received of m
						set out to out & (name of mbx) & tab & (dt as string) & tab & (sender of m) & tab & (subject of m) & tab & (message id of m) & linefeed
					end repeat
				end try
			end repeat
		end repeat
	end tell
	return out
end run
