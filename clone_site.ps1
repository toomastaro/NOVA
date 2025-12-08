# Script to clone nova.tg site content
# Requires Docker to be running and the nginx container to be active (or we run a temporary one)

Write-Host "Creating static_site directory..."
New-Item -ItemType Directory -Force -Path ".\static_site" | Out-Null

Write-Host "Cloning site content from https://nova.tg/ ..."
# We use the running nginx container to perform the wget, as it likely has wget installed (alpine usually does).
# This saves us from needing wget on the host Windows machine.
# We download to /var/www/static inside the container, which is mounted to ./static_site on host.

# Ensure the directory is clean or just overwrite? Wget mirror will handle it.
# Note: nova.tg is the source. If we run this from the server that IS nova.tg, we might get a loop if DNS points to localhost.
# But I assume we are setting this up on a server that might ideally hosting it.
# If 'nova.tg' generally points to the external IP, and we are inside the container, it should resolve to external IP.

docker compose exec nginx sh -c "wget --mirror --convert-links --adjust-extension --page-requisites --no-parent https://nova.tg/ -P /tmp/cloned_site && cp -r /tmp/cloned_site/nova.tg/* /var/www/static/ && rm -rf /tmp/cloned_site"

if ($LASTEXITCODE -eq 0) {
    Write-Host "Site successfully cloned to .\static_site"
} else {
    Write-Host "Error cloning site. Please check if nginx container is running."
}
