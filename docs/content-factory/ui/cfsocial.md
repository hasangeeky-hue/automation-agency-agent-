# Screen contract: 08 Social

Rehomed from SGA on 2026-08-13. SGA was retired; the system that decides
what goes out on social is the Content Factory, so these screens moved
here rather than becoming unreachable code. The Google hub went to the
Search OS and paid went to Media Buying, which already own those.

## Purpose
Show what this engine published to social, and how it landed, without
pretending a silent channel is a quiet one.

## User question
What goes out on social, and how did it land?

## Layout
One column. Channels first, then engagement, audience and posts, each
under its own heading, so a channel that reported nothing is visibly
absent rather than folded into a total.

## Components
Channel list, engagement figures, audience figures, post table. Each is
the SGA screen it always was, rendered inside this section's frame.

## Data
| Key | From | When absent |
|---|---|---|
| `channels` | connected social accounts | the channel is named NOT CONNECTED |
| `followers`, `reach`, `reactions` | the social insights snapshot | NOT MEASURED, with the reason |
| `posts` | what this engine published | an empty list means nothing was published, which differs from nothing measured |

## Data source
`content_engine_social_insights.load(store)`, plus the connector status
map for which accounts hold a credential. Every figure names its
account.

## Actions
None on this screen. Publishing to a social channel is an outbound
action and belongs to Distribution, behind the same named-human gate as
every other send.

## CTA
No primary CTA. This screen reports; it does not act.

## AI actions
None. An agent may propose a post in the Planner; it can never send one
from here.

## Loading
Each sub-screen renders independently, so a slow one does not blank the
others.

## Empty
"No social account is connected" names the accounts it looked for. A
connected account with no data reads NOT MEASURED, never zero.

## Error
A sub-screen that raises reports itself by name and leaves the rest
standing. The section never fails whole.

## Permissions
Read only. No credential value is ever rendered; presence only.

## State transitions
None. This screen holds no state of its own.
