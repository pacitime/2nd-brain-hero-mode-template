-- Elenca le bozze APERTE in Apple Mail (finestre di composizione): oggetto, mittente, destinatari,
-- allegati. SOLA LETTURA: non salva, non invia, non chiude nulla.
-- Uso: osascript drafts-open.applescript
on run
	set out to ""
	tell application "Mail"
		repeat with m in every outgoing message
			set toList to {}
			repeat with rc in to recipients of m
				set end of toList to address of rc
			end repeat
			set attList to {}
			try
				repeat with att in (every attachment of content of m)
					set end of attList to name of att
				end repeat
			end try
			set AppleScript's text item delimiters to ", "
			set out to out & (subject of m) & " | " & (sender of m) & " | A: " & (toList as string) & " | Allegati: " & (attList as string) & linefeed
			set AppleScript's text item delimiters to ""
		end repeat
	end tell
	return out
end run
