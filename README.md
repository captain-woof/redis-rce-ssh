# Introduction

This tool bruteforces user home directories on a Redis server, and tries to overwrite "authorized_keys" in discovered users' SSH directories.

Upon success, you can SSH in as the user via the associated private SSH key.

[Read more](https://book.hacktricks.xyz/network-services-pentesting/6379-pentesting-redis#ssh).

# Usage

```
usage: main.py [-h] [-H HOST] [-P PORT] [-p PASSWORD] [-n DATABASE] [-w USERNAMES] [--public PUBLIC] [-d DIR]

options:
  -h, --help            show this help message and exit
  -H HOST, --host HOST  Target Redis server's IP address; default: 127.0.0.1
  -P PORT, --port PORT  Target Redis server's port; default: 6379
  -p PASSWORD, --password PASSWORD
                        Login password; default: ''
  -n DATABASE, --database DATABASE
                        DB number; default: 0
  -w USERNAMES, --usernames USERNAMES
                        Usernames wordlist to use for bruteforcing
  --public PUBLIC       The public SSH key to overwrite; use 'ssh-keygen' to generate the key pair
  -d DIR, --dir DIR     User SSH directory format; must contain 'USER' placeholder; default: '/home/USER/.ssh'
```