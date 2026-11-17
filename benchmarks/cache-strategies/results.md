# Build times, 2026-11-16 22:07

Median of 7 runs; least–most in brackets. G: instructions retired, all threads (load-independent). MB: peak memory. Load average at the end: { 33.33 20.31 15.28 }.

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
| one-shot | 29 ms (28–31) · 0.80 G · 48 MB | 35 ms (33–36) · 0.82 G · 68 MB | 34 ms (33–36) · 0.82 G · 69 MB | 36 ms (34–36) · 0.86 G · 69 MB | 35 ms (33–37) · 0.83 G · 69 MB | 21 ms (21–43) · 0.46 G · 41 MB | 90 ms (89–208) · 1.43 G · 114 MB | 143 ms (141–228) · 1.82 G · 79 MB |
| one-shot --minify | 34 ms (32–37) · 0.92 G · 47 MB | 39 ms (38–41) · 0.95 G · 76 MB | 39 ms (37–40) · 0.97 G · 77 MB | 41 ms (39–42) · 0.96 G · 77 MB | 39 ms (39–42) · 0.97 G · 77 MB | 22 ms (21–22) · 0.47 G · 39 MB | 123 ms (119–129) · 1.71 G · 116 MB | 145 ms (143–146) · 1.82 G · 79 MB |
| --cache, cold | 44 ms (41–55) · 0.92 G · 77 MB | 42 ms (41–44) · 0.90 G · 76 MB | 41 ms (40–42) · 0.90 G · 73 MB | 44 ms (43–45) · 0.94 G · 78 MB | 65 ms (62–66) · 1.06 G · 102 MB | – | – | – |
| --cache, warm, unchanged | 15 ms (14–16) · 0.11 G · 14 MB | 15 ms (14–15) · 0.10 G · 12 MB | 45 ms (41–49) · 0.85 G · 84 MB | 16 ms (15–16) · 0.11 G · 14 MB | 18 ms (18–19) · 0.13 G · 19 MB | – | – | – |
| --cache, warm, one edit | 27 ms (26–34) · 0.28 G · 34 MB | 57 ms (53–115) · 1.00 G · 101 MB | 61 ms (59–67) · 0.98 G · 103 MB | 41 ms (38–46) · 0.60 G · 66 MB | 32 ms (30–37) · 0.32 G · 40 MB | – | – | – |
| watch, first build | 29 ms build · 36 ms (35–40) · 0.94 G · 86 MB · 2641 answers | 30 ms build · 37 ms (36–56) · 0.96 G · 85 MB · 2641 answers | 31 ms build · 38 ms (35–39) · 0.94 G · 87 MB · 2641 answers | 38 ms build · 45 ms (37–85) · 0.95 G · 87 MB · 2641 answers | 31 ms build · 37 ms (35–41) · 0.97 G · 87 MB · 2641 answers | 19.0 ms (18.8–20.4) | 118 ms (117–125) · 2.29 G · 130 MB | 30.1 ms (29.6–33.5) |
| watch, first, warm cache | 0 ms build · 13 ms (13–22) · 0.16 G · 17 MB · 0 answers | 0 ms build · 14 ms (13–14) · 0.19 G · 20 MB · 0 answers | 27 ms build · 50 ms (48–52) · 1.16 G · 122 MB · 2325 answers | 0 ms build · 15 ms (15–20) · 0.21 G · 23 MB · 0 answers | 1 ms build · 16 ms (15–22) · 0.17 G · 22 MB · 0 answers | – | – | – |
| watch, rebuild, one edit | 5.4 ms (4.9–10.7) · 23 answers | 19.4 ms (18.2–34.2) · 2068 answers | 5.6 ms (5.1–13.2) · 23 answers | 8.7 ms (7.9–20.3) · 23 answers | 4.7 ms (4.3–11.3) · 23 answers | 14.1 ms (11.8–15.0) | 30.9 ms (27.5–43.9) | 49.8 ms (46.7–263.3) |

## three

| | incremental | coarse | lean | versioned | tailored | esbuild | turbopack | vite |
|---|---|---|---|---|---|---|---|---|
| one-shot | 68 ms (68–70) · 1.64 G · 78 MB | 68 ms (67–70) · 1.28 G · 115 MB | 69 ms (68–69) · 1.26 G · 116 MB | 69 ms (68–71) · 1.22 G · 116 MB | 71 ms (69–74) · 1.23 G · 116 MB | 48 ms (47–49) · 0.52 G · 44 MB | 152 ms (149–152) · 1.34 G · 152 MB | 195 ms (190–196) · 2.19 G · 77 MB |
| one-shot --minify | 94 ms (93–96) · 3.60 G · 80 MB | 92 ms (91–93) · 3.25 G · 159 MB | 93 ms (91–95) · 3.26 G · 160 MB | 95 ms (93–98) · 3.21 G · 161 MB | 95 ms (94–97) · 3.27 G · 161 MB | 59 ms (57–71) · 0.58 G · 43 MB | 206 ms (205–208) · 1.86 G · 152 MB | 196 ms (193–197) · 2.21 G · 77 MB |
| --cache, cold | 77 ms (76–78) · 1.33 G · 126 MB | 76 ms (75–82) · 1.32 G · 125 MB | 74 ms (73–76) · 1.36 G · 122 MB | 80 ms (78–86) · 1.31 G · 126 MB | 111 ms (108–120) · 1.56 G · 172 MB | – | – | – |
| --cache, warm, unchanged | 15 ms (15–17) · 0.11 G · 14 MB | 14 ms (13–14) · 0.09 G · 12 MB | 76 ms (74–79) · 1.29 G · 132 MB | 16 ms (15–16) · 0.11 G · 14 MB | 20 ms (19–21) · 0.15 G · 26 MB | – | – | – |
| --cache, warm, one edit | 44 ms (43–53) · 0.48 G · 69 MB | 93 ms (89–96) · 1.42 G · 151 MB | 94 ms (90–97) · 1.49 G · 151 MB | 45 ms (43–54) · 0.49 G · 69 MB | 79 ms (71–146) · 0.81 G · 125 MB | – | – | – |
| watch, first build | 88 ms build · 94 ms (93–96) · 1.54 G · 129 MB · 239 answers | 88 ms build · 94 ms (94–99) · 1.63 G · 127 MB · 239 answers | 88 ms build · 95 ms (93–96) · 1.59 G · 128 MB · 239 answers | 90 ms build · 98 ms (95–100) · 1.57 G · 129 MB · 239 answers | 92 ms build · 99 ms (97–103) · 1.56 G · 128 MB · 239 answers | 43.6 ms (42.4–45.2) | 179 ms (175–205) · 1.54 G · 173 MB | 78.5 ms (77.5–79.7) |
| watch, first, warm cache | 0 ms build · 14 ms (14–19) · 0.14 G · 20 MB · 0 answers | 0 ms build · 14 ms (13–14) · 0.15 G · 21 MB · 0 answers | 83 ms build · 101 ms (99–103) · 1.69 G · 156 MB · 221 answers | 0 ms build · 16 ms (14–26) · 0.14 G · 20 MB · 0 answers | 1 ms build · 17 ms (17–21) · 0.17 G · 28 MB · 0 answers | – | – | – |
| watch, rebuild, one edit | 17.6 ms (17.4–33.0) · 32 answers | 40.8 ms (39.4–95.7) · 201 answers | 17.6 ms (17.4–25.3) · 32 answers | 18.6 ms (17.3–25.4) · 32 answers | 18.0 ms (17.2–38.7) · 32 answers | 40.4 ms (38.9–41.9) | – | 101.3 ms (94.2–105.6) |

## datefns

| | incremental | coarse | lean | versioned | tailored | esbuild | turbopack | vite |
|---|---|---|---|---|---|---|---|---|
| one-shot | 27 ms (26–28) · 0.65 G · 31 MB | 41 ms (41–43) · 1.09 G · 52 MB | 42 ms (42–44) · 1.08 G · 54 MB | 43 ms (42–44) · 1.16 G · 54 MB | 43 ms (41–53) · 1.07 G · 53 MB | 26 ms (25–29) · 0.46 G · 34 MB | 56 ms (55–68) · 0.75 G · 73 MB | 140 ms (138–142) · 1.74 G · 79 MB |
| one-shot --minify | 43 ms (42–46) · 1.57 G · 31 MB | 58 ms (56–65) · 1.99 G · 57 MB | 58 ms (57–71) · 2.03 G · 58 MB | 59 ms (58–60) · 2.06 G · 58 MB | 59 ms (56–70) · 2.01 G · 58 MB | 26 ms (26–27) · 0.48 G · 34 MB | 65 ms (62–65) · 0.82 G · 74 MB | 141 ms (139–153) · 1.74 G · 77 MB |
| --cache, cold | 55 ms (53–57) · 1.24 G · 67 MB | 66 ms (65–79) · 1.21 G · 66 MB | 49 ms (49–51) · 1.17 G · 58 MB | 60 ms (57–63) · 1.28 G · 66 MB | 70 ms (65–73) · 1.34 G · 77 MB | – | – | – |
| --cache, warm, unchanged | 19 ms (18–176) · 0.13 G · 17 MB | 24 ms (17–27) · 0.11 G · 15 MB | 56 ms (52–69) · 1.16 G · 70 MB | 19 ms (18–22) · 0.13 G · 17 MB | 20 ms (20–23) · 0.13 G · 19 MB | – | – | – |
| --cache, warm, one edit | 32 ms (32–37) · 0.43 G · 35 MB | 76 ms (70–87) · 1.61 G · 87 MB | 73 ms (70–81) · 1.32 G · 88 MB | 50 ms (48–57) · 0.72 G · 50 MB | 37 ms (33–40) · 0.45 G · 38 MB | – | – | – |
| watch, first build | 40 ms build · 47 ms (46–48) · 1.27 G · 86 MB · 8005 answers | 40 ms build · 47 ms (46–47) · 1.26 G · 86 MB · 8005 answers | 41 ms build · 47 ms (47–48) · 1.27 G · 88 MB · 8005 answers | 41 ms build · 48 ms (47–49) · 1.33 G · 87 MB · 8005 answers | 41 ms build · 48 ms (47–49) · 1.30 G · 88 MB · 8005 answers | 22.0 ms (19.9–23.3) | 74 ms (74–75) · 1.01 G · 80 MB | 32.0 ms (31.0–64.4) |
| watch, first, warm cache | 0 ms build · 16 ms (15–22) · 0.21 G · 20 MB · 0 answers | 0 ms build · 16 ms (16–17) · 0.23 G · 23 MB · 0 answers | 38 ms build · 64 ms (61–65) · 1.58 G · 124 MB · 7042 answers | 0 ms build · 17 ms (15–23) · 0.23 G · 23 MB · 0 answers | 0 ms build · 17 ms (16–23) · 0.22 G · 23 MB · 0 answers | – | – | – |
| watch, rebuild, one edit | 8.6 ms (7.4–14.3) · 23 answers | 29.2 ms (27.8–51.0) · 6161 answers | 9.2 ms (8.3–17.9) · 23 answers | 19.1 ms (17.8–37.8) · 23 answers | 8.0 ms (7.2–15.6) · 23 answers | 14.7 ms (14.0–17.1) | 26.6 ms (21.9–28.8) | 47.3 ms (44.5–53.6) |

## rx

| | incremental | coarse | lean | versioned | tailored | esbuild | turbopack | vite |
|---|---|---|---|---|---|---|---|---|
| one-shot | 25 ms (24–26) · 0.56 G · 32 MB | 36 ms (35–37) · 0.85 G · 50 MB | 36 ms (35–37) · 0.86 G · 52 MB | 36 ms (35–37) · 0.85 G · 51 MB | 37 ms (35–37) · 0.86 G · 52 MB | 21 ms (21–22) · 0.38 G · 28 MB | 48 ms (47–49) · 0.51 G · 69 MB | 138 ms (137–139) · 1.60 G · 72 MB |
| one-shot --minify | 27 ms (26–36) · 0.72 G · 34 MB | 39 ms (38–42) · 1.11 G · 55 MB | 39 ms (38–49) · 1.14 G · 57 MB | 40 ms (40–48) · 1.16 G · 56 MB | 40 ms (40–50) · 1.12 G · 57 MB | 22 ms (21–22) · 0.39 G · 29 MB | 59 ms (58–61) · 0.59 G · 69 MB | 140 ms (137–143) · 1.61 G · 73 MB |
| --cache, cold | 46 ms (46–48) · 0.94 G · 58 MB | 45 ms (44–47) · 0.94 G · 57 MB | 41 ms (41–42) · 0.91 G · 53 MB | 47 ms (46–48) · 0.98 G · 58 MB | 56 ms (54–59) · 1.05 G · 67 MB | – | – | – |
| --cache, warm, unchanged | 17 ms (17–18) · 0.12 G · 16 MB | 16 ms (16–19) · 0.10 G · 15 MB | 48 ms (45–51) · 0.92 G · 63 MB | 17 ms (17–18) · 0.12 G · 16 MB | 18 ms (17–20) · 0.13 G · 18 MB | – | – | – |
| --cache, warm, one edit | 30 ms (29–33) · 0.39 G · 34 MB | 61 ms (57–73) · 1.15 G · 74 MB | 62 ms (58–67) · 1.06 G · 82 MB | 43 ms (42–49) · 0.59 G · 45 MB | 32 ms (31–35) · 0.40 G · 36 MB | – | – | – |
| watch, first build | 34 ms build · 41 ms (40–43) · 1.04 G · 81 MB · 7169 answers | 34 ms build · 41 ms (40–45) · 1.02 G · 80 MB · 7169 answers | 35 ms build · 42 ms (41–43) · 1.06 G · 82 MB · 7169 answers | 35 ms build · 42 ms (41–43) · 1.05 G · 81 MB · 7169 answers | 36 ms build · 42 ms (41–44) · 1.05 G · 82 MB · 7169 answers | 17.4 ms (16.4–18.2) | 60 ms (59–61) · 0.72 G · 74 MB | 28.9 ms (28.5–29.2) |
| watch, first, warm cache | 0 ms build · 15 ms (14–21) · 0.20 G · 19 MB · 0 answers | 0 ms build · 14 ms (14–15) · 0.20 G · 20 MB · 0 answers | 33 ms build · 56 ms (54–59) · 1.32 G · 112 MB · 6435 answers | 0 ms build · 15 ms (15–22) · 0.21 G · 22 MB · 0 answers | 0 ms build · 16 ms (15–22) · 0.20 G · 21 MB · 0 answers | – | – | – |
| watch, rebuild, one edit | 6.3 ms (6.0–14.4) · 23 answers | 23.7 ms (22.6–41.6) · 5800 answers | 7.9 ms (6.9–14.3) · 23 answers | 15.9 ms (15.1–22.7) · 23 answers | 7.1 ms (5.6–12.6) · 23 answers | 11.1 ms (10.3–12.1) | 25.2 ms (21.2–31.3) | 44.9 ms (42.8–46.4) |

## manyzod

| | incremental | coarse | lean | versioned | tailored | esbuild | turbopack | vite |
|---|---|---|---|---|---|---|---|---|
| one-shot | 130 ms (127–132) · 6.37 G · 338 MB | 191 ms (188–195) · 7.35 G · 649 MB | 195 ms (189–200) · 7.45 G · 657 MB | 196 ms (193–196) · 7.18 G · 655 MB | 200 ms (195–233) · 7.38 G · 657 MB | 106 ms (105–109) · 4.84 G · 332 MB | 754 ms (743–760) · 15.64 G · 572 MB | 237 ms (235–240) · 6.35 G · 287 MB |
| one-shot --minify | 191 ms (188–193) · 8.64 G · 343 MB | 257 ms (253–268) · 9.56 G · 739 MB | 264 ms (259–270) · 9.76 G · 744 MB | 267 ms (259–276) · 9.75 G · 743 MB | 264 ms (261–266) · 9.46 G · 744 MB | 108 ms (106–111) · 4.86 G · 307 MB | 1174 ms (1167–1191) · 18.65 G · 568 MB | 248 ms (245–252) · 6.38 G · 302 MB |
| --cache, cold | 279 ms (276–283) · 8.21 G · 751 MB | 273 ms (267–282) · 8.17 G · 726 MB | 241 ms (239–252) · 7.97 G · 713 MB | 288 ms (281–305) · 8.13 G · 750 MB | 509 ms (502–511) · 9.56 G · 975 MB | – | – | – |
| --cache, warm, unchanged | 79 ms (78–84) · 0.79 G · 101 MB | 66 ms (66–70) · 0.62 G · 91 MB | 315 ms (279–343) · 7.99 G · 787 MB | 81 ms (80–83) · 0.79 G · 101 MB | 107 ms (103–108) · 1.02 G · 164 MB | – | – | – |
| --cache, warm, one edit | 153 ms (145–194) · 2.06 G · 257 MB | 431 ms (411–480) · 10.13 G · 915 MB | 457 ms (440–491) · 9.49 G · 918 MB | 254 ms (244–291) · 5.31 G · 548 MB | 182 ms (178–244) · 2.33 G · 322 MB | – | – | – |
| watch, first build | 207 ms build · 214 ms (212–217) · 8.24 G · 841 MB · 30047 answers | 206 ms build · 213 ms (211–216) · 8.12 G · 838 MB · 30047 answers | 208 ms build · 215 ms (214–217) · 8.35 G · 843 MB · 30047 answers | 210 ms build · 217 ms (216–220) · 8.13 G · 841 MB · 30047 answers | 210 ms build · 217 ms (214–225) · 8.16 G · 844 MB · 30047 answers | 135.9 ms (125.1–139.5) | 899 ms (887–922) · 23.75 G · 408 MB | 153.7 ms (151.5–155.2) |
| watch, first, warm cache | 1 ms build · 60 ms (60–102) · 1.08 G · 140 MB · 0 answers | 1 ms build · 81 ms (80–82) · 1.56 G · 174 MB · 0 answers | 199 ms build · 346 ms (325–366) · 10.96 G · 1167 MB · 26399 answers | 1 ms build · 84 ms (83–126) · 1.71 G · 219 MB · 0 answers | 3 ms build · 88 ms (86–130) · 1.32 G · 205 MB · 0 answers | – | – | – |
| watch, rebuild, one edit | 28.9 ms (25.2–62.3) · 23 answers | 175.4 ms (172.1–305.6) · 23171 answers | 31.0 ms (26.2–112.7) · 23 answers | 98.0 ms (71.3–138.3) · 23 answers | 26.3 ms (25.5–67.8) · 23 answers | 110.4 ms (94.7–114.9) | 35.6 ms (33.0–105.9) | 145.1 ms (137.6–158.4) |
