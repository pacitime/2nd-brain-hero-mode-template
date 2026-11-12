-- Crea una BOZZA nuova in Apple Mail da un indirizzo scelto. NON invia: in questo script non c'e'
-- nessun comando di invio (CLAUDE.md §5: bozze si', invio a mano). La finestra di composizione resta
-- aperta, cosi' l'utente rilegge e invia lui.
-- Uso: osascript draft-new.applescript "Nome <mittente@dominio>" "<destinatario>[,<destinatario>...]" "<oggetto>" "<corpo>" ["<allegato>[,<allegato>...]"]
-- Destinatari e allegati (percorsi assoluti) separati da virgola; gli allegati sono facoltativi.
-- Il mittente deve essere un indirizzo di un account di Mail (account-add-alias.applescript per aggiungerlo).
-- Output: oggetto, mittente, destinatari e allegati della bozza salvata, per verificare.
on run argv
	set senderAddr to item 1 of argv
	set subj to item 3 of argv
	set bodyText to item 4 of argv
	set AppleScript's text item delimiters to ","
	set toAddrs to text items of (item 2 of argv)
	set attPaths to {}
	if (count of argv) > 4 then set attPaths to text items of (item 5 of argv)
	set AppleScript's text item delimiters to ""

	tell application "Mail"
		set m to make new outgoing message with properties {subject:subj, content:bodyText, visible:true}
		set sender of m to senderAddr
		repeat with a in toAddrs
			tell m to make new to recipient at end of to recipients with properties {address:(a as string)}
		end repeat
		repeat with p in attPaths
			tell content of m to make new attachment with properties {file name:(POSIX file (p as string)) as alias} at after last paragraph
		end repeat
		-- la finestra si popola in modo asincrono: senza attesa il salvataggio perde i campi
		delay 2
		save m
		set toList to {}
		repeat with rc in to recipients of m
			set end of toList to address of rc
		end repeat
		set attList to {}
		-- un messaggio in uscita non espone "mail attachments": gli allegati stanno nel suo content
		try
			repeat with att in (every attachment of content of m)
				set end of attList to name of att
			end repeat
		end try
		set out to (subject of m) & " | " & (sender of m)
	end tell
	set AppleScript's text item delimiters to ", "
	return out & " | A: " & (toList as string) & " | Allegati: " & (attList as string)
end run
