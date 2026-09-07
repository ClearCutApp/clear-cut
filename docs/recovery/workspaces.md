# Teams, private assignments and production settings

Workspace owners/admins manage membership and invitations. Only owners can change
owner membership, and at least one owner must remain. Membership and invitation
mutations require expected versions and append audit records. Private project
management also requires an explicit project management grant; an unassigned
organization administrator cannot inspect or assign that private project.

Invitations are seven-day single-use links bound to the invited verified email.
The server stores only a token hash and returns the secret once; the browser puts
it in the URL fragment so HTTP requests do not carry it in their URL. Authentication
and email verification preserve the local return destination. Acceptance is
idempotent for the same still-active member and creates no project grant/index.
There is no mailbox sending: the owner shares the link manually.

Revocation immediately denies membership. Rejoining requires a new invitation and
increments a membership epoch. Project grants record the epoch they belong to;
old grants therefore do not revive when the person rejoins. Authorization and
transactional draft/revision, analysis, report and clearance writes check this
epoch. Reassigning a rejoined member is an explicit new project-access mutation.
Fresh projects use the creator's current epoch.

Team controls live at /team; private assignments and production settings live at
/projects/:id/settings. The clearance editor's assignee selector includes active
members explicitly assigned to that project. Assignment versions prevent lost
updates. Historical assignment IDs remain visible if the directory is unavailable.

Production settings save title, primary jurisdiction and up to 30 named filming
locations (country plus city/region/address/description) using expected versions.
New-project choices match Argentina, Mexico, Spain, Colombia, USA and Canada;
historical jurisdiction labels remain readable. A location entry is not proof of
local permitting coverage. Missing research remains a gap.

Analysis requests freeze locations, selected legal jurisdiction and settings
version. Later settings changes never alter queued inputs. Results disclose
settings changes; fixed reports record production-context changes at capture.
Human reconfirmation rejects changed locations both before and inside its
generation/item write transaction.

Offline tests cover hashed invitation creation/acceptance, expiry/revocation/wrong
email, same-user replay, no implicit projects, last-owner protection, unassigned
admin/foreign-target denial, stale mutations, rejoin isolation, draft permission
rechecks, immutable queued location context, UI conflicts and late project responses.
Real Firebase acceptance, concurrent Firestore transactions and the deployed team
journey remain unverified. This does not resolve the Firebase terms blocker.
