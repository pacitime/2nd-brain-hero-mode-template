-- LettorePosta: esegue UNO degli AppleScript di sola lettura della posta (pull, sent, read) per conto
-- di loop_sync.py e ne scrive l'esito in un file. Nient'altro: niente bozze, niente allegati, niente
-- invio. Gli script ammessi sono copiati dentro l'app da build.sh.
--
-- PERCHE'. Da launchd i figli di autopilot sono attribuiti, per i permessi di macOS, all'interprete
-- python che li lancia: la sua richiesta «controllare Mail» compare quando nessuno e' davanti al
-- Mac, scade senza risposta, e macOS puo' non lasciare piu' riattivare l'interruttore. Un'app aperta
-- con `open` e' invece responsabile di se stessa: ha un permesso suo, chiesto una volta, che non si
-- perde quando Python viene aggiornato.
--
-- Uso (lo chiama loop_sync.py):
--   open -g -W -n -a LettorePosta.app --args <file-esito> <pull|sent|read> [argomenti...]
-- Esito: «OK» + a capo + l'output dello script, oppure «ERR <numero> <messaggio>».
use AppleScript version "2.4"
use framework "Foundation"
use scripting additions

on run
	set argv to (current application's NSProcessInfo's processInfo()'s arguments()) as list
	if (count of argv) < 3 then return
	set outPath to item 2 of argv
	set nome to item 3 of argv
	set params to {}
	if (count of argv) > 3 then set params to items 4 thru -1 of argv

	if nome is not in {"pull", "sent", "read"} then
		set res to "ERR 0 script non ammesso: " & nome
	else
		try
			set f to ((path to me as text) & "Contents:Resources:lettore:" & nome & ".applescript")
			set res to "OK" & linefeed & (run script (f as alias) with parameters params)
		on error msg number n
			set res to "ERR " & n & " " & msg
		end try
	end if

	-- `as POSIX file`, non `POSIX file outPath`: con `use framework` la seconda forma fallisce
	-- (-1700, «current application» → «class fsrf») e l'app esce in silenzio senza scrivere.
	set fh to open for access (outPath as POSIX file) with write permission
	set eof fh to 0
	write res to fh as «class utf8»
	close access fh
end run
