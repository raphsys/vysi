# 04 — États des représentations

Toute représentation est décrite par un `RepresentationSlot` :

- `available` ;
- `partial` ;
- `not_requested` ;
- `not_applicable` ;
- `unsupported` ;
- `blocked_by_policy` ;
- `failed`.

`available` et `partial` exigent une référence hashée. Les autres états interdisent une référence de
contenu mais exigent au moins un code de raison, sauf `not_requested` et `not_applicable`.

Une référence `null` sans état est interdite.
