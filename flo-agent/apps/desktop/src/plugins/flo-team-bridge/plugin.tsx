/**
 * Private bridge to the bundled Flo Team backend API.
 *
 * Desktop plugin REST is scoped to the desktop plugin id by design. The
 * backend router lives under `/api/plugins/flo-team`, so keep this tiny
 * contribution as the owner of that namespace rather than reaching across
 * from the Ashley-facing `flo` plugin.
 */

import type { HermesPlugin } from '@hermes/plugin-sdk'

import { bindFloActions } from '@/plugins/flo/actions-api'

const plugin: HermesPlugin = {
  id: 'flo-team',
  name: 'Flo Local Workflows',
  description: 'Private local workflow bridge for Flo’s existing backend actions.',
  register(ctx) {
    ctx.onDispose(bindFloActions(ctx.rest))
  }
}

export default plugin
