-- Elenca le email INVIATE negli ultimi N giorni, su tutti gli account di Apple Mail. SOLA LETTURA:
-- non invia, non risponde, non sposta nulla.
-- Uso: osascript sent.applescript [giorni]   (default 2)
-- Output: una riga per email, campi separati da TAB →
--   account <TAB> mailbox <TAB> data <TAB> oggetto <TAB> destinatari <TAB> message-id
-- Il corpo intero si prende con read.applescript passando il message-id (l'ultimo campo).
on run argv
	set nDays to 2
	if (count of argv) > 0 then set nDays to (item 1 of argv) as integer
	set cutoff to (current date) - (nDays * days)
	set out to ""
	tell application "Mail"
		repeat with acct in every account
			repeat with mbx in (every mailbox of acct)
				set n to name of mbx
				if n contains "Sent" or n contains "Inviat" or n contains "sent" then
					try
						set hits to (messages of mbx whose date sent > cutoff)
						repeat with m in hits
							set rcpts to ""
							repeat with r in to recipients of m
								set rcpts to rcpts & (address of r) & " "
							end repeat
							set out to out & (name of acct) & tab & n & tab & ((date sent of m) as string) & tab & (subject of m) & tab & rcpts & tab & (message id of m) & linefeed
						end repeat
					end try
				end if
			end repeat
		end repeat
	end tell
	return out
end run
