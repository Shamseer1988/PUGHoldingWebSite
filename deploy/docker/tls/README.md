# Drop your Cloudflare Origin Certificate here, then bring the stack up.
#
# Required files (on the EC2 host, NOT committed to git):
#
#     origin.crt   — full Cloudflare-issued cert chain
#     origin.key   — matching private key (chmod 600)
#
# Generation:
#   Cloudflare dashboard → your zone → SSL/TLS → Origin Server →
#   Create Certificate. Pick RSA 2048 or ECDSA, 15-year validity,
#   list parisunitedgroup.com + *.parisunitedgroup.com as hostnames.
#   Save the displayed cert/key — they're only shown once.
#
# After dropping them in, harden permissions:
#
#     sudo chmod 644 origin.crt
#     sudo chmod 600 origin.key
#
# .gitignore at the repo root already excludes *.crt + *.key so a
# stray ``git add`` can't leak them.
