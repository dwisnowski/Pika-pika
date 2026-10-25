# Cloudflare Access

Internet access to Pika goes through `https://pika.wildideazone.com`. Cloudflare Access sits in front of that hostname. A visitor must sign in, and their email must be on the **Owner only** policy, before any request reaches the BeagleBone.

The web app itself has no login. A device on the same LAN as the board can open `http://<board-ip>:8888` without Access. That path is not reachable from the public internet through the tunnel.

## Approve another person

1. Open the Zero Trust dashboard and go to **Access controls** → **Applications** → **Pika**.
2. Edit the **Owner only** policy.
3. Add an Include rule for their exact email. Leave the decision as **Allow**.
4. They open `https://pika.wildideazone.com` and sign in with a one-time PIN sent to that email, or as a Cloudflare account member using that same email.

Access denies them until that email is on the policy. Do not add an Everyone rule, a Bypass policy, or a second public hostname that has no Access application of its own.

Two later changes would remove this gate: setting the `pika.wildideazone.com` DNS record to DNS-only, or deleting the Pika Access application. Leave the record proxied, and leave the application in place.

The tunnel token stays in `.cloudflared.env` on the machine that installs the tunnel. Do not commit it.
