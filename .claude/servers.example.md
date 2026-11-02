# Server access configuration (TEMPLATE)

Copy this file to `.claude/servers.local.md` (gitignored) and fill it in.
Never put passwords, tokens or private keys here: access is by SSH key only.
The `booking-api-ops` agent reads `.claude/servers.local.md` to know how to reach the servers.

## primary
- host: booking-api.es
- ssh: `ssh <your_user>@booking-api.es`
- project_path: /home/ubuntu/booking_api
- account: <your_user>
- privileges: <e.g. sudo NOPASSWD | none>
- notes: <e.g. run git as ubuntu: `sudo -u ubuntu git ...`; docker needs sudo>

## secondary
- host: booking-api.ddns.net
- ssh: `ssh <your_user>@booking-api.ddns.net`
- project_path: <path of the project on that server for your account>
- account: <your_user>
- privileges: <e.g. read-only on the project folder, no sudo, no docker>
- notes: <restrictions the agent must respect>
