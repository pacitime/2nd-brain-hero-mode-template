-- Crea una BOZZA di risposta a tutti a un'email di Apple Mail. NON invia: in questo script non c'e'
-- nessun comando di invio (CLAUDE.md §5: bozze si', invio a mano). La finestra di composizione resta
-- aperta, cosi' l'utente rilegge e invia lui.
-- Uso: osascript draft-reply.applescript "<NomeAccount>" "<message-id>" "<corpo della risposta>"
-- Il message-id e' l'ultimo campo di pull.applescript. Il messaggio originale viene citato sotto.
on run argv
	set acctName to item 1 of argv
	set wanted to item 2 of argv
	set bodyText to item 3 of argv

	tell application "Mail"
		set acct to first account whose name is acctName
		-- prima INBOX; se non c'e' (Gmail archiviata: sta in "Tutti i messaggi"/"All Mail"),
		-- cerca negli altri mailbox dell'account
		set m to missing value
		try
			set m to first message of (first mailbox of acct whose name is "INBOX") whose message id is wanted
		end try
		if m is missing value then
			repeat with mb in (every mailbox of acct)
				try
					set m to first message of mb whose message id is wanted
					exit repeat
				end try
			end repeat
		end if
		set orig to content of m
		set dt to date received of m
		set snd to sender of m
		set r to reply m with opening window and reply to all
		-- la finestra si popola in modo asincrono: senza attesa il contenuto viene sovrascritto
		delay 2
		set quoted to ""
		repeat with p in paragraphs of orig
			set quoted to quoted & "> " & p & linefeed
		end repeat
		set content of r to bodyText & linefeed & linefeed & "Il giorno " & (dt as string) & " " & snd & " ha scritto:" & linefeed & quoted
		delay 1
		save r
		set toList to {}
		repeat with rc in to recipients of r
			set end of toList to address of rc
		end repeat
		set ccList to {}
		repeat with rc in cc recipients of r
			set end of ccList to address of rc
		end repeat
		set subj to subject of r
	end tell
	set AppleScript's text item delimiters to ", "
	return "Oggetto: " & subj & linefeed & "A: " & (toList as string) & linefeed & "CC: " & (ccList as string)
end run
