# Design rules

The conventions behind these dashboards. They keep a wall tablet calm and a phone uncluttered.

## Layout

- **Sections views everywhere.** Tablet: up to 4 columns. Phone: 1 column.
- **Home answers three questions at a glance:** what's the weather, does anything need attention, and what's on.
- **The attention strip is empty most of the time.** It lists only things to act on: an open door or window, a battery under 15 %, lights on with nobody home. Add your own lines, but keep each one actionable.
- **Every room is one tap from Home**, and every room page has a back arrow to Rooms.

## Tablet

- **Kiosk mode only on touch tablets**, detected in the browser — never on phones or computers. An admin toggle brings the header back for editing.
- **Screensaver:** a photo slideshow with a large clock after 3 minutes idle. Use people-free photos if visitors see the panel.
- **Big targets:** tiles at least half a column wide; no hold-only actions for things guests need.

## Phone

- **Never kiosk mode, never a screensaver.** A phone must always be able to leave the dashboard.
- **Bottom tab bar** (navbar-card, floating) for the main pages. Every page except Home is a subview, so the header shows ← back instead of tabs.
- **Fewer cards than the tablet:** the clock is dropped from the weather card (the phone has one) and the forecast is 3 days.

## Look

- **Wall Panel theme:** frosted-glass cards (`backdrop-filter: blur(18px)`) over a photo or gradient view background, 20 px corners, soft shadows; works in light and dark mode.
- **Colour means state:** amber = lights on, red = needs action, grey = idle. Don't colour for decoration.

## Safety

- **Anything that unlocks, disarms or opens asks for confirmation.** Disarming from a phone without a code is a deliberate opt-in, not a default.
- **Garage doors and gates:** confirmation on every action.
