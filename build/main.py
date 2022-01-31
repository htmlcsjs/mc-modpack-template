#!/usr/bin/env python3

"""build client & server bundles"""

# if there is a problem with building, please let htmlcsjs know
import os
import sys
import shutil
import subprocess
import requests
import json
import hashlib
import argparse


def parse_args():
    parser = argparse.ArgumentParser(prog="build", description=__doc__)
    parser.add_argument("--sha", action="store_true", help="append git hash to zips")
    parser.add_argument("--name", type=str, help="append name to zips")
    parser.add_argument("--retries", type=int, default=3, help="download attempts before failure")
    parser.add_argument("--clean", action="store_true", help="clean output dirs")
    return parser.parse_args()


args = parse_args()


modlist = []
basePath = os.path.normpath(os.path.realpath(__file__)[:-7] + "..")
copyDirs = ["/scripts", "/resources", "/config", "/mods", "/structures"]
serverCopyDirs = ["/scripts", "/config", "/mods", "/structures"]
modURLlist = []

if args.clean:
    shutil.rmtree(basePath + "/buildOut/client/overrides", ignore_errors=True)
    shutil.rmtree(basePath + "/buildOut/server", ignore_errors=True)
    shutil.rmtree(basePath + "/mods", ignore_errors=True)
    sys.exit(0)

sha = ""
if args.sha:
    try:
        p = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, cwd=basePath)
        sha = p.stdout.strip().decode("utf-8")
    except Exception as e:
        print("could not determine git sha, skipping")

with open(basePath + "/manifest.json") as file:
    manifest = json.load(file)

cachepath = os.path.join(basePath, "buildOut", "modcache")


def mkdirs(path):
    try:
        os.makedirs(path)
    except Exception as e:
        print("%s exists, skipping" % (path))


mkdirs(basePath + "/buildOut/client/overrides")
mkdirs(basePath + "/buildOut/server")
mkdirs(basePath + "/mods")
mkdirs(cachepath)  # /buildOut/modcach

# if we downloaded mods before, add them to the cache
prev = basePath + "/buildOut/server/mods"
cached = 0
if os.path.isdir(prev):
    for f in os.listdir(prev):
        # don't waste time copying mods to the cache that are already there
        if os.path.exists(os.path.join(cachepath, f)):
            continue
        cached += 1
        shutil.copy2(os.path.join(prev, f), os.path.join(cachepath, f))

if cached > 0:
    print("cached %d mod downloads in %s" % (cached, cachepath))

for mod in manifest["externalDeps"]:
    with open(basePath + "/mods/" + mod["url"].split("/")[-1], "w+b") as jar:
        for i in range(args.retries + 1):
            if i == args.retries:
                raise Exception("Download failed")

            r = requests.get(mod["url"])

            hash = hashlib.sha256(jar.read()).hexdigest()
            if str(hash) == mod["hash"]: TODO fix
                jar.write(r.content)
                modlist.append(mod["name"])
                print("hash succsessful")
                break
            else:
                print("hash unsuccsessful")
                print("use", str(hash), "this if it is consistant across runs")
                pass

for dir in copyDirs:
    try:
        shutil.copytree(basePath + dir, basePath + "/buildOut/client/overrides" + dir)
    except Exception as e:
        print("Directory exists, skipping")
print("directories copied to buildOut/client")

archive = "buildOut/client"
if sha:
    archive = "%s-%s" % (archive, sha)

shutil.copy(basePath + "/manifest.json", basePath + "/buildOut/client/manifest.json")
shutil.make_archive(archive, "zip", basePath + "/buildOut/client")
print('client zip "%s.zip"  made' % (archive))

for mod in manifest["files"]:
    url = "https://cursemeta.dries007.net/" + str(mod["projectID"]) + "/" + str(mod["fileID"]) + ".json"
    r = requests.get(url)
    metadata = json.loads(r.text)
    modlist.append(metadata["FileName"])
    modURLlist.append(metadata["DownloadURL"])

print("modlist compiled")

with open(basePath + "/buildOut/modlist.html", "w") as file:
    data = "<html><body><h1>GregTech CEu Community Pack modlist</h1><ul>"
    for mod in modlist:
        data += "<li>" + mod + "</li>"
    data += "</ul></body></html>"
    file.write(data)

print("modlist.html done")

shutil.copy(basePath + "/manifest.json", basePath + "/buildOut/server/manifest.json")
shutil.copy(basePath + "/LICENSE", basePath + "/buildOut/server/LICENSE")
shutil.copy(basePath + "/launch.sh", basePath + "/buildOut/server/launch.sh")
shutil.copy(basePath + "/launch.bat", basePath + "/buildOut/server/launch.bat")

for dir in serverCopyDirs:
    try:
        shutil.copytree(basePath + dir, basePath + "/buildOut/server" + dir)
    except Exception as e:
        print("Directory exists, skipping")
print("directories copied to buildOut/server")

for mod in modURLlist:
    jarname = mod.split("/")[-1]

    if os.path.exists(os.path.join(cachepath, jarname)):
        shutil.copy2(os.path.join(cachepath, jarname), os.path.join(basePath, "buildOut", "server", "mods", jarname))
        print("%s loaded from cache" % (mod))
        continue

    with open(basePath + "/buildOut/server/mods/" + jarname, "w+b") as jar:
        r = requests.get(mod)
        jar.write(r.content)
        print(mod + " Downloaded")
print("Mods Downloaded")

with open(basePath + "/buildOut/server/forge-installer.jar", "w+b") as jar:
    forgeVer = manifest["minecraft"]["modLoaders"][0]["id"].split("-")[-1]
    mcVer = manifest["minecraft"]["version"]
    url = (
        "https://maven.minecraftforge.net/net/minecraftforge/forge/"
        + mcVer
        + "-"
        + forgeVer
        + "/forge-"
        + mcVer
        + "-"
        + forgeVer
        + "-installer.jar"
    )
    r = requests.get(url)
    jar.write(r.content)
print("Forge installer Downloaded")

# TODO: make a portable version between versions

vanilla = basePath + "/buildOut/server/minecraft_server.1.12.2.jar"

if not os.path.isfile(vanilla):
    with open(basePath + "/buildOut/server/minecraft_server.1.12.2.jar", "w+b") as jar:
        url = "https://launcher.mojang.com/v1/objects/886945bfb2b978778c3a0288fd7fab09d315b25f/server.jar"
        r = requests.get(url)
        jar.write(r.content)
    print("Vanilla Downloaded")

subprocess.run(["java", "-jar", "forge-installer.jar", "--installServer"], cwd=basePath + "/buildOut/server/")
print("Forge Installed")

try:
    os.remove(basePath + "/buildOut/server/forge-installer.jar")
except Exception as e:
    print("Couldn't delete forge-installer.jar: %s" % (e))
try:
    os.remove(basePath + "/buildOut/server/forge-installer.jar.log")
except Exception as e:
    print("Couldn't delete forge-installer.jar.log: %s" % (e))

archive = "buildOut/server"
if sha:
    archive = "%s-%s" % (archive, sha)
shutil.make_archive(archive, "zip", basePath + "/buildOut/server")
print('server zip "%s.zip" made' % (archive))
print("done")
