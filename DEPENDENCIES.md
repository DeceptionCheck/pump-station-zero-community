# Runtime dependency graph

All imports terminate inside this source directory or Python's standard library.

```text
community.server
  community.session
    sim.station                         existing simulator
    decoy_modbus.server
      decoy_modbus.register_map          existing finite protocol map
    community.events                    bounded basic projection
    community.hmi                       existing industrial HTML/SVG
    community.wire                      fixed loopback request/readback
    community.report                    deterministic report, loaded on Finish
  community.hmi
  community.report
  community/assets/console.html
  community/assets/console.css
  community/assets/console.js
```

There is no import of the full analyst, brain, application runtime, operator wall, private mount or adjacent checkout. There is no optional intelligence interface that ordinary installation must discover or satisfy. No package performs a model download or a remote HTTP request. The only client sockets are the fixed request/readback to this process's own loopback Modbus listener and the browser's same-origin HTTP requests. The offline acceptance suite exercises the actual journey with non-loopback socket connections denied.
