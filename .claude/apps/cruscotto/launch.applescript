-- Lanciatore del Cruscotto: accende il server locale (se è spento) e apre la board in una
-- finestra pulita (Chrome o Brave in modalità app; altrimenti il browser predefinito).
-- Si usa compilato in un'app da doppio click (comando nel README.md di questa cartella).
-- L'app compilata deve restare in questa cartella: è da qui che ricava dov'è il vault.
on run
	-- Questo file (o l'app compilata) sta in <vault>/.claude/apps/cruscotto: il vault è tre livelli sopra.
	set myDir to do shell script "dirname " & quoted form of POSIX path of (path to me)
	set vaultDir to do shell script "cd " & quoted form of (myDir & "/../../..") & " && pwd"
	-- Un'app non eredita il PATH del terminale: si aggiungono le cartelle di Homebrew.
	set goVault to "cd " & quoted form of vaultDir & " && export PATH=/opt/homebrew/bin:/usr/local/bin:$PATH && "
	-- L'indirizzo lo dice il server (la porta sta in .claude/config/brain.json): una fonte sola.
	set appUrl to do shell script goVault & "python3 .claude/apps/cruscotto/server.py --url"
	-- Avvia il server solo se non risponde già
	do shell script goVault & "(curl -s -o /dev/null --max-time 2 " & appUrl & "/api/tasks || (nohup python3 .claude/apps/cruscotto/server.py >/dev/null 2>&1 &)); sleep 1"
	-- Apri la finestra-app
	try
		do shell script "open -na 'Google Chrome' --args --app=" & appUrl
	on error
		try
			do shell script "open -na 'Brave Browser' --args --app=" & appUrl
		on error
			do shell script "open " & appUrl
		end try
	end try
end run
