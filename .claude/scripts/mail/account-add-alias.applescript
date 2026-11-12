-- Aggiunge un indirizzo (alias) a un account di Apple Mail, cosi' lo si puo' scegliere come mittente.
-- Non tocca credenziali ne' server: modifica solo l'elenco "email addresses" dell'account in Mail.
-- Reversibile da Mail > Impostazioni > Account > Indirizzo email > Modifica indirizzi email.
-- Uso: osascript account-add-alias.applescript "<NomeAccount>" "<alias@dominio>"
-- Output: l'elenco degli indirizzi dell'account dopo la modifica.
on run argv
	set acctName to item 1 of argv
	set newAddr to item 2 of argv

	tell application "Mail"
		set acct to first account whose name is acctName
		set addrs to email addresses of acct
		if addrs does not contain newAddr then
			set end of addrs to newAddr
			set email addresses of acct to addrs
		end if
		set result_ to email addresses of acct
	end tell
	set AppleScript's text item delimiters to ", "
	return result_ as string
end run
