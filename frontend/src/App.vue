<template>
  <v-app>
    <v-app-bar color="primary" density="comfortable">
      <v-app-bar-title>I2C Web Reader</v-app-bar-title>
      <v-spacer />
      <v-chip size="small" variant="flat" class="mr-2">{{ statusText }}</v-chip>
    </v-app-bar>

    <v-main>
      <v-container class="py-6" fluid>
        <v-row dense>
          <v-col cols="12" md="5">
            <v-card variant="elevated">
              <v-card-title>Connection</v-card-title>
              <v-card-text>
                <v-alert v-if="error" type="error" variant="tonal" class="mb-3">
                  {{ error }}
                </v-alert>

                <v-select
                  v-model="config.pins_preset"
                  :items="presets"
                  item-title="label"
                  item-value="key"
                  label="I2C preset (bus + pins)"
                  density="comfortable"
                />

                <v-select
                  v-model="config.transport"
                  :items="transports"
                  label="Transport"
                  density="comfortable"
                  class="mt-2"
                />

                <v-row dense>
                  <v-col cols="12" sm="6">
                    <v-text-field v-model="addressHex" label="I2C address (hex)" density="comfortable" />
                  </v-col>
                  <v-col cols="12" sm="6">
                    <v-text-field v-model.number="config.bus" label="Bus" density="comfortable" type="number" />
                  </v-col>
                </v-row>

                <v-row dense>
                  <v-col cols="12" sm="6">
                    <v-text-field v-model="registerHex" label="Register (hex)" density="comfortable" />
                  </v-col>
                  <v-col cols="12" sm="6">
                    <v-select
                      v-model="config.register_width"
                      :items="[1, 2]"
                      label="Register width (bytes)"
                      density="comfortable"
                    />
                  </v-col>
                </v-row>

                <v-row dense>
                  <v-col cols="12" sm="6">
                    <v-text-field v-model.number="config.read_length" label="Read length (bytes)" density="comfortable" type="number" />
                  </v-col>
                  <v-col cols="12" sm="6">
                    <v-text-field v-model.number="config.poll_hz" label="Poll rate (Hz)" density="comfortable" type="number" />
                  </v-col>
                </v-row>

                <v-row class="mt-2" dense>
                  <v-col cols="12" sm="6">
                    <v-btn block color="primary" variant="flat" @click="saveConfig">Save config</v-btn>
                  </v-col>
                  <v-col cols="12" sm="3">
                    <v-btn block color="success" variant="flat" @click="start">Start</v-btn>
                  </v-col>
                  <v-col cols="12" sm="3">
                    <v-btn block color="error" variant="flat" @click="stop">Stop</v-btn>
                  </v-col>
                </v-row>

                <v-row class="mt-2" dense>
                  <v-col cols="12">
                    <v-btn block variant="tonal" @click="applyMpuExample">
                      Apply MPU-9150 example (0x68, reg 0x3B, len 14, int16 BE)
                    </v-btn>
                  </v-col>
                </v-row>

                <v-row class="mt-2" dense>
                  <v-col cols="12">
                    <v-btn block variant="tonal" @click="applyMagExample">
                      Apply AK8975C magnetometer (0x0C, reg 0x02, len 8, int16 LE)
                    </v-btn>
                  </v-col>
                </v-row>
              </v-card-text>
            </v-card>

            <v-card class="mt-4" variant="elevated">
              <v-card-title>Schema</v-card-title>
              <v-card-text>
                <v-row dense class="mb-2">
                  <v-col cols="12" sm="6">
                    <v-btn block variant="tonal" @click="addField">Add field</v-btn>
                  </v-col>
                  <v-col cols="12" sm="6">
                    <v-btn block color="primary" variant="flat" @click="saveSchema">Save schema</v-btn>
                  </v-col>
                </v-row>

                <v-alert v-if="schemaInfo" type="info" variant="tonal" class="mb-3">
                  Total bytes: {{ schemaInfo.total_bytes }}
                </v-alert>

                <v-table density="compact">
                  <thead>
                    <tr>
                      <th>Name</th>
                      <th>Type</th>
                      <th>Count</th>
                      <th>Endian</th>
                      <th />
                    </tr>
                  </thead>
                  <tbody>
                    <tr v-for="(f, idx) in schema.fields" :key="idx">
                      <td style="min-width: 140px">
                        <v-text-field v-model="f.name" density="compact" hide-details />
                      </td>
                      <td style="min-width: 120px">
                        <v-select v-model="f.type" :items="ctypes" density="compact" hide-details />
                      </td>
                      <td style="max-width: 90px">
                        <v-text-field v-model.number="f.count" density="compact" type="number" hide-details />
                      </td>
                      <td style="min-width: 110px">
                        <v-select v-model="f.endianness" :items="endianness" density="compact" hide-details />
                      </td>
                      <td style="width: 44px">
                        <v-btn variant="text" @click="removeField(idx)">Remove</v-btn>
                      </td>
                    </tr>
                  </tbody>
                </v-table>
              </v-card-text>
            </v-card>
          </v-col>

          <v-col cols="12" md="7">
            <v-card variant="elevated">
              <v-card-title class="d-flex align-center">
                <span>Live frames</span>
                <v-spacer />
                <v-btn size="small" variant="tonal" @click="refreshFrames">Refresh</v-btn>
              </v-card-title>
              <v-card-text>
                <v-expansion-panels variant="accordion" class="mb-3">
                  <v-expansion-panel>
                    <v-expansion-panel-title>Smoothing (display only)</v-expansion-panel-title>
                    <v-expansion-panel-text>
                      <v-row dense>
                        <v-col cols="12" sm="4">
                          <v-switch v-model="smoothing.enabled" label="Enable smoothing" inset />
                        </v-col>
                        <v-col cols="12" sm="4">
                          <v-select
                            v-model="smoothing.mode"
                            :items="['ema', 'moving_average']"
                            label="Mode"
                            density="comfortable"
                            :disabled="!smoothing.enabled"
                          />
                        </v-col>
                        <v-col cols="12" sm="4">
                          <v-text-field
                            v-model.number="smoothing.param"
                            :label="smoothing.mode === 'ema' ? 'EMA alpha (0..1)' : 'Window (samples)'"
                            density="comfortable"
                            type="number"
                            :disabled="!smoothing.enabled"
                          />
                        </v-col>
                      </v-row>
                      <div class="text-caption">
                        This does not change the raw bytes; it only smooths the decoded numbers you see here.
                      </div>
                    </v-expansion-panel-text>
                  </v-expansion-panel>
                </v-expansion-panels>

                <v-alert v-if="streamStatus" type="info" variant="tonal" class="mb-3">
                  {{ streamStatus }}
                </v-alert>

                <v-table density="compact">
                  <thead>
                    <tr>
                      <th>Time</th>
                      <th>Raw (hex)</th>
                      <th>Decoded / Errors</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr v-for="(fr, idx) in frames" :key="idx">
                      <td style="white-space: nowrap">{{ formatTs(fr.ts_unix) }}</td>
                      <td style="font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace">
                        {{ fr.raw_hex }}
                      </td>
                      <td>
                        <div v-if="fr.error" class="text-error">I2C error: {{ fr.error }}</div>
                        <div v-else-if="fr.decode_error" class="text-warning">Decode error: {{ fr.decode_error }}</div>
                        <pre v-else style="margin: 0; white-space: pre-wrap">{{ displayDecoded(fr) }}</pre>
                      </td>
                    </tr>
                  </tbody>
                </v-table>
              </v-card-text>
            </v-card>
          </v-col>
        </v-row>
      </v-container>
    </v-main>
  </v-app>
</template>

<script setup>
import { onMounted, reactive, ref, computed } from 'vue'
import { apiGet, apiPut, apiPost, makeWsUrl } from './api'

const error = ref('')
const streamStatus = ref('')

const presets = ref([])

const config = reactive({
  enabled: false,
  transport: 'linux_i2c',
  pins_preset: 'i2c-1',
  bus: 1,
  address: 0,
  register: 0,
  register_width: 1,
  read_length: 16,
  poll_hz: 10.0,
  setup_writes: [],
  cycle_write: null,
  cycle_delay_ms: 10,
})

const schema = reactive({
  fields: [],
})

const schemaInfo = ref(null)

const ctypes = ['uint8', 'uint16', 'uint32', 'uint64', 'int8', 'int16', 'int32', 'int64']
const endianness = ['little', 'big']
const transports = ['linux_i2c', 'mock_mpu9150']

const frames = ref([])

const smoothing = reactive({
  enabled: false,
  mode: 'ema', // 'ema' | 'moving_average'
  param: 0.2, // EMA alpha or window size
})

// State for smoothing across frames.
const emaState = reactive({})
const windowState = reactive({})

const addressHex = computed({
  get: () => `0x${Number(config.address).toString(16)}`,
  set: (v) => {
    const n = parseInt(String(v).replace(/^0x/i, ''), 16)
    if (!Number.isNaN(n)) config.address = n
  },
})

const registerHex = computed({
  get: () => `0x${Number(config.register).toString(16)}`,
  set: (v) => {
    const n = parseInt(String(v).replace(/^0x/i, ''), 16)
    if (!Number.isNaN(n)) config.register = n
  },
})

const statusText = computed(() => (config.enabled ? 'running' : 'stopped'))

function formatTs(tsUnix) {
  try {
    return new Date(tsUnix * 1000).toLocaleTimeString()
  } catch {
    return String(tsUnix)
  }
}

function setErr(e) {
  error.value = e?.message ?? String(e)
}

function isPlainNumber(x) {
  return typeof x === 'number' && Number.isFinite(x)
}

function clamp(x, lo, hi) {
  return Math.min(hi, Math.max(lo, x))
}

function smoothNumber(key, x) {
  if (!smoothing.enabled) return x
  if (!isPlainNumber(x)) return x

  if (smoothing.mode === 'ema') {
    const alpha = clamp(Number(smoothing.param) || 0.2, 0.0, 1.0)
    const prev = emaState[key]
    const next = prev === undefined ? x : alpha * x + (1 - alpha) * prev
    emaState[key] = next
    return next
  }

  const win = Math.max(1, Math.floor(Number(smoothing.param) || 5))
  const arr = windowState[key] ?? (windowState[key] = [])
  arr.push(x)
  if (arr.length > win) arr.splice(0, arr.length - win)
  const sum = arr.reduce((a, b) => a + b, 0)
  return sum / arr.length
}

function smoothDecoded(decoded) {
  if (!decoded || typeof decoded !== 'object') return decoded
  const out = {}
  for (const [k, v] of Object.entries(decoded)) {
    if (isPlainNumber(v)) {
      out[k] = smoothNumber(k, v)
    } else if (Array.isArray(v)) {
      out[k] = v.map((vv, idx) => smoothNumber(`${k}[${idx}]`, vv))
    } else {
      out[k] = v
    }
  }
  return out
}

function displayDecoded(frame) {
  return smoothing.enabled ? smoothDecoded(frame.decoded) : frame.decoded
}

async function loadInitial() {
  error.value = ''
  presets.value = await apiGet('/api/presets')
  Object.assign(config, await apiGet('/api/config'))
  const s = await apiGet('/api/schema')
  schemaInfo.value = { total_bytes: s.total_bytes }
  schema.fields = (s.schema?.fields ?? []).map((x) => ({ ...x }))
  await refreshFrames()
}

async function saveConfig() {
  try {
    error.value = ''
    const resp = await apiPut('/api/config', { ...config })
    Object.assign(config, resp.config)
  } catch (e) {
    setErr(e)
  }
}

async function saveSchema() {
  try {
    error.value = ''
    const resp = await apiPut('/api/schema', { fields: schema.fields })
    schemaInfo.value = { total_bytes: resp.total_bytes }
  } catch (e) {
    setErr(e)
  }
}

function addField() {
  schema.fields.push({ name: `field${schema.fields.length}`, type: 'uint8', count: 1, endianness: 'little' })
}

function removeField(idx) {
  schema.fields.splice(idx, 1)
}

async function start() {
  try {
    error.value = ''
    await apiPost('/api/control/start')
    config.enabled = true
  } catch (e) {
    setErr(e)
  }
}

async function stop() {
  try {
    error.value = ''
    await apiPost('/api/control/stop')
    config.enabled = false
  } catch (e) {
    setErr(e)
  }
}

async function refreshFrames() {
  try {
    const resp = await apiGet('/api/frames?limit=200')
    frames.value = (resp.frames ?? []).reverse()
  } catch (e) {
    setErr(e)
  }
}

async function applyMpuExample() {
  try {
    error.value = ''
    const resp = await apiPost('/api/examples/mpu9150/apply')
    Object.assign(config, resp.config)
    schemaInfo.value = { total_bytes: resp.total_bytes }
    schema.fields = (resp.schema?.fields ?? []).map((x) => ({ ...x }))
    await refreshFrames()
  } catch (e) {
    setErr(e)
  }
}

async function applyMagExample() {
  try {
    error.value = ''
    const resp = await apiPost('/api/examples/ak8975c/apply')
    Object.assign(config, resp.config)
    schemaInfo.value = { total_bytes: resp.total_bytes }
    schema.fields = (resp.schema?.fields ?? []).map((x) => ({ ...x }))
    await refreshFrames()
  } catch (e) {
    setErr(e)
  }
}

function startStream() {
  streamStatus.value = 'connecting websocket…'
  const ws = new WebSocket(makeWsUrl('/api/stream'))
  let pingTimer = null
  ws.onopen = () => {
    streamStatus.value = 'websocket connected'
    // Send pings so server keepalive loop can receive.
    pingTimer = setInterval(() => {
      try {
        ws.send('ping')
      } catch {
        // ignore
      }
    }, 30000)
  }
  ws.onmessage = (evt) => {
    try {
      const fr = JSON.parse(evt.data)
      frames.value.unshift(fr)
      if (frames.value.length > 500) frames.value.length = 500
    } catch {
      // ignore
    }
  }
  ws.onclose = () => {
    streamStatus.value = 'websocket disconnected; retrying…'
    try {
      if (pingTimer) clearInterval(pingTimer)
    } catch {
      // ignore
    }
    setTimeout(startStream, 2000)
  }
  ws.onerror = () => {
    // onclose will handle retry
  }
}

onMounted(async () => {
  await loadInitial()
  startStream()
})
</script>
