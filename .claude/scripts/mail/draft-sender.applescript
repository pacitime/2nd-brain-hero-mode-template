-- Cambia il MITTENTE di una bozza gia' aperta in Apple Mail (trovata per oggetto) e la risalva.
-- NON invia: nessun comando di invio qui dentro (CLAUDE.md §5: bozze si', invio a mano).
-- Uso: osascript draft-sender.applescript "<oggetto esatto>" "Nome <indirizzo@dominio>"
-- Output: oggetto e mittente di ogni bozza aperta, per verificare che il cambio abbia preso.
on run argv
	set wantedSubject to item 1 of argv
	set newSender to item 2 of argv

	tell application "Mail"
		repeat with r in (every outgoing message whose subject is wantedSubject)
			set sender of r to newSender
			save r
		end repeat
		delay 1
		set out to ""
		repeat with r in every outgoing message
			set out to out & (subject of r) & " | " & (sender of r) & linefeed
		end repeat
	end tell
	return out
end run
