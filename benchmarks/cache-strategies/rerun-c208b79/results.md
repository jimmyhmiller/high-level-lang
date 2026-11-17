# Build times, 2026-11-17 00:07

Median of 7 runs; least–most in brackets. G: instructions retired, all threads (load-independent). MB: peak memory. Load average at the end: { 59.18 38.58 23.92 }.

- **incremental** (esb): `/Users/jimmyhmiller/Documents/Code/projects/high-level-lang/out/bin-o3-cachebench/esb` --pipeline=full
- **coarse** (esb): `/Users/jimmyhmiller/Documents/Code/projects/high-level-lang/out/bin-o3-cachebench/esb` --pipeline=full --strategy=coarse
- **lean** (esb): `/Users/jimmyhmiller/Documents/Code/projects/high-level-lang/out/bin-o3-cachebench/esb` --pipeline=full --strategy=lean
- **versioned** (esb): `/Users/jimmyhmiller/Documents/Code/projects/high-level-lang/out/bin-o3-cachebench/esb` --pipeline=full --strategy=versioned
- **tailored** (esb): `/Users/jimmyhmiller/Documents/Code/projects/high-level-lang/out/bin-o3-cachebench/esb` --pipeline=full --strategy=tailored
- **esbuild** (esbuild): `/Users/jimmyhmiller/Documents/Code/projects/high-level-lang/tests/node_modules/esbuild` 
- **turbopack** (turbopack): `/Users/jimmyhmiller/Documents/Code/projects/high-level-lang/out/bin/turbopack-cli-4ebb2b7` 
- **vite** (vite): `/Users/jimmyhmiller/Documents/Code/projects/high-level-lang/benchmarks/bundlers/node_modules/vite` 

## zod

| | incremental | coarse | lean | versioned | tailored | esbuild | turbopack | vite |
|---|---|---|---|---|---|---|---|---|
| one-shot | 30 ms (29–49) · 0.81 G · 48 MB | 37 ms (36–38) · 0.85 G · 68 MB | 35 ms (34–38) · 0.85 G · 69 MB | 34 ms (33–36) · 0.86 G · 69 MB | 35 ms (34–38) · 0.85 G · 69 MB | 24 ms (23–26) · 0.46 G · 41 MB | 108 ms (92–219) · 1.44 G · 114 MB | 167 ms (147–228) · 1.82 G · 77 MB |
| one-shot --minify | 34 ms (34–45) · 0.93 G · 47 MB | 43 ms (41–48) · 0.94 G · 76 MB | 57 ms (40–84) · 0.98 G · 76 MB | 42 ms (41–43) · 0.93 G · 77 MB | 39 ms (38–40) · 0.95 G · 77 MB | 24 ms (23–24) · 0.47 G · 39 MB | 151 ms (137–177) · 1.71 G · 115 MB | 152 ms (145–164) · 1.81 G · 78 MB |
| --cache, cold | 46 ms (44–57) · 0.96 G · 78 MB | 49 ms (46–53) · 0.93 G · 76 MB | 52 ms (40–66) · 0.91 G · 73 MB | 51 ms (47–51) · 0.90 G · 78 MB | 65 ms (60–66) · 1.05 G · 102 MB | – | – | – |
| --cache, warm, unchanged | 15 ms (15–19) · 0.11 G · 14 MB | 15 ms (14–21) · 0.10 G · 12 MB | 46 ms (41–51) · 0.89 G · 84 MB | 16 ms (15–17) · 0.11 G · 14 MB | 19 ms (19–19) · 0.13 G · 19 MB | – | – | – |
| --cache, warm, one edit | 28 ms (26–34) · 0.27 G · 34 MB | 63 ms (54–76) · 1.04 G · 102 MB | 63 ms (60–64) · 1.00 G · 104 MB | 42 ms (39–44) · 0.59 G · 67 MB | 44 ms (38–80) · 0.31 G · 40 MB | – | – | – |
| watch, first build | 36 ms build · 43 ms (37–48) · 0.93 G · 86 MB · 2641 answers | 35 ms build · 42 ms (38–48) · 1.00 G · 85 MB · 2641 answers | 32 ms build · 39 ms (37–41) · 0.95 G · 86 MB · 2641 answers | 32 ms build · 38 ms (37–40) · 0.99 G · 86 MB · 2641 answers | 36 ms build · 43 ms (39–52) · 0.96 G · 86 MB · 2641 answers | 21.1 ms (20.3–24.1) | 192 ms (150–232) · 2.28 G · 131 MB | – |
| watch, first, warm cache | 0 ms build · 13 ms (13–20) · 0.15 G · 17 MB · 0 answers | 0 ms build · 15 ms (14–16) · 0.19 G · 20 MB · 0 answers | 31 ms build · 53 ms (50–65) · 1.19 G · 121 MB · 2325 answers | 0 ms build · 16 ms (16–22) · 0.21 G · 23 MB · 0 answers | 1 ms build · 16 ms (16–23) · 0.17 G · 22 MB · 0 answers | – | – | – |
| watch, rebuild, one edit | 5.4 ms (4.4–11.2) · 23 answers | 20.0 ms (18.7–39.7) · 2068 answers | 5.5 ms (4.9–13.2) · 23 answers | 8.5 ms (7.5–20.2) · 23 answers | 5.8 ms (4.7–12.0) · 23 answers | 15.1 ms (13.9–18.2) | 124.4 ms (46.0–169.0) | – |

## three

| | incremental | coarse | lean | versioned | tailored | esbuild | turbopack | vite |
|---|---|---|---|---|---|---|---|---|
| one-shot | 70 ms (68–105) · 1.36 G · 78 MB | 68 ms (66–90) · 1.74 G · 114 MB | 69 ms (66–89) · 1.71 G · 116 MB | 86 ms (73–101) · 1.39 G · 115 MB | 71 ms (70–76) · 1.73 G · 116 MB | 49 ms (47–55) · 0.52 G · 44 MB | 165 ms (150–185) · 1.34 G · 152 MB | 208 ms (202–234) · 2.20 G · 77 MB |
| one-shot --minify | 98 ms (94–102) · 3.47 G · 79 MB | 93 ms (92–109) · 3.32 G · 159 MB | 95 ms (91–102) · 2.79 G · 160 MB | 103 ms (98–148) · 1.79 G · 160 MB | 104 ms (97–116) · 3.21 G · 160 MB | 58 ms (57–69) · 0.59 G · 43 MB | 212 ms (206–239) · 1.87 G · 167 MB | 202 ms (198–213) · 2.22 G · 77 MB |
| --cache, cold | 78 ms (76–95) · 1.84 G · 126 MB | 79 ms (76–104) · 1.79 G · 125 MB | 75 ms (73–82) · 1.84 G · 122 MB | 84 ms (81–124) · 1.60 G · 126 MB | 171 ms (118–223) · 1.80 G · 172 MB | – | – | – |
| --cache, warm, unchanged | 18 ms (15–24) · 0.11 G · 14 MB | 15 ms (14–18) · 0.09 G · 12 MB | 77 ms (74–84) · 1.77 G · 133 MB | 16 ms (15–16) · 0.11 G · 14 MB | 27 ms (21–42) · 0.15 G · 26 MB | – | – | – |
| --cache, warm, one edit | 44 ms (43–59) · 0.48 G · 69 MB | 94 ms (90–137) · 1.91 G · 152 MB | 94 ms (91–101) · 1.95 G · 151 MB | 52 ms (46–59) · 0.48 G · 69 MB | 94 ms (78–192) · 0.81 G · 128 MB | – | – | – |
| watch, first build | 89 ms build · 95 ms (93–108) · 2.62 G · 128 MB · 239 answers | 89 ms build · 96 ms (94–103) · 2.47 G · 127 MB · 239 answers | 89 ms build · 96 ms (93–124) · 2.68 G · 128 MB · 239 answers | 95 ms build · 102 ms (96–108) · 2.02 G · 128 MB · 239 answers | 99 ms build · 113 ms (100–167) · 1.84 G · 128 MB · 239 answers | 43.7 ms (42.6–70.3) | 207 ms (194–361) · 1.54 G · 161 MB | 151.3 ms (95.9–253.6) |
| watch, first, warm cache | 0 ms build · 14 ms (14–26) · 0.14 G · 20 MB · 0 answers | 0 ms build · 14 ms (13–25) · 0.15 G · 20 MB · 0 answers | 84 ms build · 102 ms (99–122) · 2.77 G · 156 MB · 221 answers | 0 ms build · 15 ms (14–19) · 0.14 G · 20 MB · 0 answers | 1 ms build · 17 ms (17–21) · 0.17 G · 27 MB · 0 answers | – | – | – |
| watch, rebuild, one edit | 18.2 ms (18.1–45.8) · 32 answers | 42.9 ms (40.5–94.5) · 201 answers | 18.6 ms (17.9–26.5) · 32 answers | 18.7 ms (18.3–33.9) · 32 answers | 18.4 ms (18.0–38.7) · 32 answers | 41.1 ms (38.7–55.1) | – | 2718.6 ms (132.9–3050.2) |

## datefns

| | incremental | coarse | lean | versioned | tailored | esbuild | turbopack | vite |
|---|---|---|---|---|---|---|---|---|
| one-shot | 30 ms (27–67) · 0.64 G · 31 MB | 42 ms (40–51) · 1.09 G · 53 MB | 43 ms (41–44) · 1.13 G · 54 MB | 42 ms (41–43) · 1.17 G · 54 MB | 42 ms (42–44) · 1.12 G · 53 MB | 26 ms (25–27) · 0.46 G · 34 MB | 56 ms (56–59) · 0.75 G · 73 MB | 140 ms (137–142) · 1.69 G · 78 MB |
| one-shot --minify | 46 ms (44–47) · 1.38 G · 31 MB | 62 ms (58–77) · 1.91 G · 57 MB | 61 ms (58–63) · 1.93 G · 58 MB | 59 ms (56–69) · 2.09 G · 58 MB | 61 ms (58–70) · 1.98 G · 57 MB | 26 ms (26–29) · 0.48 G · 35 MB | 67 ms (64–73) · 0.82 G · 74 MB | 138 ms (138–149) · 1.70 G · 78 MB |
| --cache, cold | 57 ms (56–59) · 1.18 G · 66 MB | 55 ms (54–58) · 1.25 G · 66 MB | 50 ms (49–87) · 1.22 G · 58 MB | 60 ms (55–87) · 1.24 G · 67 MB | 66 ms (65–69) · 1.25 G · 77 MB | – | – | – |
| --cache, warm, unchanged | 18 ms (17–19) · 0.13 G · 17 MB | 17 ms (17–18) · 0.11 G · 15 MB | 56 ms (52–60) · 1.15 G · 69 MB | 18 ms (17–24) · 0.13 G · 17 MB | 19 ms (19–20) · 0.13 G · 19 MB | – | – | – |
| --cache, warm, one edit | 33 ms (31–36) · 0.39 G · 36 MB | 71 ms (68–86) · 1.63 G · 87 MB | 73 ms (67–75) · 1.32 G · 87 MB | 49 ms (47–69) · 0.70 G · 50 MB | 34 ms (33–38) · 0.42 G · 38 MB | – | – | – |
| watch, first build | 44 ms build · 52 ms (48–69) · 1.27 G · 86 MB · 8005 answers | 40 ms build · 48 ms (46–50) · 1.34 G · 86 MB · 8005 answers | 44 ms build · 51 ms (47–58) · 1.29 G · 87 MB · 8005 answers | 42 ms build · 49 ms (47–52) · 1.36 G · 86 MB · 8005 answers | 42 ms build · 50 ms (48–64) · 1.34 G · 88 MB · 8005 answers | 22.3 ms (20.6–24.1) | 171 ms (81–190) · 1.01 G · 80 MB | 44.4 ms (43.2–184.3) |
| watch, first, warm cache | 0 ms build · 16 ms (15–22) · 0.21 G · 20 MB · 0 answers | 0 ms build · 17 ms (16–23) · 0.23 G · 23 MB · 0 answers | 40 ms build · 68 ms (61–94) · 1.64 G · 124 MB · 7042 answers | 0 ms build · 16 ms (15–23) · 0.23 G · 24 MB · 0 answers | 0 ms build · 17 ms (16–24) · 0.22 G · 23 MB · 0 answers | – | – | – |
| watch, rebuild, one edit | 7.6 ms (6.6–27.7) · 23 answers | 29.7 ms (27.7–56.0) · 6161 answers | 8.6 ms (7.2–16.6) · 23 answers | 18.2 ms (17.3–28.6) · 23 answers | 8.4 ms (6.9–14.5) · 23 answers | 14.5 ms (14.0–15.7) | 1660.0 ms (472.0–2007.1) | 208.3 ms (78.5–1825.3) |

## rx

| | incremental | coarse | lean | versioned | tailored | esbuild | turbopack | vite |
|---|---|---|---|---|---|---|---|---|
| one-shot | 28 ms (24–39) · 0.63 G · 32 MB | 38 ms (36–42) · 0.89 G · 50 MB | 39 ms (37–49) · 0.89 G · 51 MB | 37 ms (36–50) · 0.94 G · 51 MB | 38 ms (36–41) · 0.91 G · 51 MB | 21 ms (21–23) · 0.37 G · 30 MB | 48 ms (47–50) · 0.51 G · 69 MB | 139 ms (138–157) · 1.60 G · 71 MB |
| one-shot --minify | 30 ms (29–36) · 0.73 G · 34 MB | 45 ms (40–68) · 1.20 G · 55 MB | 48 ms (40–55) · 1.19 G · 56 MB | 57 ms (42–74) · 1.47 G · 55 MB | 42 ms (41–47) · 1.24 G · 56 MB | 22 ms (21–23) · 0.38 G · 28 MB | 58 ms (57–63) · 0.58 G · 69 MB | 141 ms (139–144) · 1.61 G · 73 MB |
| --cache, cold | 47 ms (46–70) · 1.00 G · 58 MB | 47 ms (45–47) · 1.01 G · 58 MB | 43 ms (41–45) · 0.99 G · 53 MB | 49 ms (49–60) · 0.95 G · 59 MB | 55 ms (54–57) · 1.07 G · 67 MB | – | – | – |
| --cache, warm, unchanged | 17 ms (17–18) · 0.12 G · 16 MB | 17 ms (16–17) · 0.10 G · 15 MB | 54 ms (51–85) · 1.15 G · 63 MB | 18 ms (17–19) · 0.12 G · 16 MB | 18 ms (18–19) · 0.12 G · 18 MB | – | – | – |
| --cache, warm, one edit | 32 ms (30–34) · 0.36 G · 34 MB | 64 ms (58–71) · 1.20 G · 75 MB | 64 ms (60–65) · 1.13 G · 81 MB | 44 ms (43–50) · 0.63 G · 44 MB | 35 ms (32–81) · 0.40 G · 36 MB | – | – | – |
| watch, first build | 36 ms build · 43 ms (41–58) · 1.11 G · 80 MB · 7169 answers | 37 ms build · 44 ms (42–88) · 1.02 G · 79 MB · 7169 answers | 35 ms build · 42 ms (41–44) · 1.13 G · 81 MB · 7169 answers | 38 ms build · 45 ms (43–58) · 1.08 G · 80 MB · 7169 answers | 40 ms build · 46 ms (43–58) · 1.03 G · 82 MB · 7169 answers | 17.8 ms (16.0–19.3) | 108 ms (74–167) · 0.72 G · 74 MB | 42.0 ms (40.3–44.0) |
| watch, first, warm cache | 0 ms build · 15 ms (14–21) · 0.20 G · 19 MB · 0 answers | 0 ms build · 14 ms (14–19) · 0.20 G · 20 MB · 0 answers | 36 ms build · 59 ms (57–72) · 1.47 G · 112 MB · 6435 answers | 0 ms build · 16 ms (16–25) · 0.21 G · 22 MB · 0 answers | 0 ms build · 16 ms (15–28) · 0.20 G · 21 MB · 0 answers | – | – | – |
| watch, rebuild, one edit | 6.5 ms (5.7–14.8) · 23 answers | 25.8 ms (24.4–44.0) · 5800 answers | 8.0 ms (6.5–14.7) · 23 answers | 17.1 ms (15.6–32.6) · 23 answers | 8.2 ms (6.8–19.9) · 23 answers | 10.8 ms (10.6–11.3) | 1555.2 ms (356.0–1870.3) | 2230.5 ms (2020.0–2398.0) |

## manyzod

| | incremental | coarse | lean | versioned | tailored | esbuild | turbopack | vite |
|---|---|---|---|---|---|---|---|---|
| one-shot | 147 ms (140–164) · 6.40 G · 338 MB | 210 ms (201–428) · 7.13 G · 648 MB | 213 ms (207–220) · 7.32 G · 658 MB | 245 ms (214–287) · 7.08 G · 657 MB | 214 ms (196–276) · 7.38 G · 658 MB | 120 ms (115–152) · 4.85 G · 333 MB | 2151 ms (779–3417) · 15.66 G · 566 MB | 347 ms (295–516) · 6.48 G · 286 MB |
| one-shot --minify | 202 ms (197–219) · 8.72 G · 343 MB | 305 ms (285–587) · 8.96 G · 737 MB | 322 ms (271–397) · 9.50 G · 744 MB | 329 ms (283–466) · 8.99 G · 743 MB | 312 ms (272–364) · 9.81 G · 745 MB | 123 ms (114–131) · 4.85 G · 307 MB | 1563 ms (1360–3485) · 18.73 G · 551 MB | 362 ms (298–381) · 6.47 G · 301 MB |
| --cache, cold | 309 ms (297–324) · 8.21 G · 751 MB | 308 ms (297–317) · 7.92 G · 723 MB | 296 ms (264–379) · 7.91 G · 716 MB | 322 ms (307–357) · 7.96 G · 752 MB | 583 ms (542–619) · 9.59 G · 978 MB | – | – | – |
| --cache, warm, unchanged | 84 ms (79–87) · 0.79 G · 102 MB | 72 ms (70–84) · 0.64 G · 91 MB | 369 ms (299–437) · 8.04 G · 788 MB | 81 ms (79–85) · 0.79 G · 101 MB | 108 ms (105–135) · 1.01 G · 163 MB | – | – | – |
| --cache, warm, one edit | 156 ms (153–237) · 1.98 G · 258 MB | 471 ms (458–517) · 9.99 G · 918 MB | 571 ms (509–613) · 9.23 G · 918 MB | 323 ms (310–451) · 5.53 G · 549 MB | 188 ms (181–275) · 2.30 G · 321 MB | – | – | – |
| watch, first build | 237 ms build · 245 ms (239–253) · 8.16 G · 836 MB · 30047 answers | 241 ms build · 248 ms (240–271) · 7.98 G · 837 MB · 30047 answers | 461 ms build · 478 ms (343–533) · 7.81 G · 839 MB · 30047 answers | 244 ms build · 252 ms (234–270) · 8.05 G · 836 MB · 30047 answers | 243 ms build · 251 ms (243–261) · 8.07 G · 843 MB · 30047 answers | 152.5 ms (147.0–156.2) | 1360 ms (943–1446) · 24.10 G · 404 MB | 554.2 ms (323.8–693.8) |
| watch, first, warm cache | 1 ms build · 61 ms (60–103) · 1.10 G · 141 MB · 0 answers | 1 ms build · 88 ms (86–95) · 1.59 G · 173 MB · 0 answers | 350 ms build · 518 ms (466–621) · 10.60 G · 1168 MB · 26399 answers | 1 ms build · 86 ms (85–125) · 1.71 G · 218 MB · 0 answers | 4 ms build · 89 ms (87–130) · 1.34 G · 205 MB · 0 answers | – | – | – |
| watch, rebuild, one edit | 30.2 ms (24.8–63.1) · 23 answers | 178.1 ms (173.9–360.4) · 23171 answers | 31.4 ms (29.4–124.6) · 23 answers | 96.5 ms (77.8–149.6) · 23 answers | 28.1 ms (25.1–69.7) · 23 answers | 117.9 ms (111.1–132.2) | 1739.6 ms (817.2–1796.8) | 1768.4 ms (1545.7–2061.7) |
