# Small-model capability boundary report

Pass threshold per cell: **80%** (5 questions per cell, so 4/5 correct).  
Boundary = highest level reached with all lower levels also passing.

## Boundary per model

| config       |   params_B | Knowledge   | Concept   | Calculation   | Applied reasoning   | Instruction following   |   overall_acc |   format_ok |   median_s |   median_tok_s |   hit_max_tokens |
|:-------------|-----------:|:------------|:----------|:--------------|:--------------------|:------------------------|--------------:|------------:|-----------:|---------------:|-----------------:|
| qwen3.5:0.8b |        0.8 | L1          | L4        | L2            | L3                  | L1                      |          0.69 |        0.94 |        0.6 |          235.6 |                2 |
| qwen3.5:2b   |        2   | L3          | L3        | L3            | L3                  | L3                      |          0.8  |        0.98 |        1.4 |          149.3 |                1 |
| gemma4:e2b   |        2.3 | L3          | L4        | L3            | L3                  | L4                      |          0.87 |        0.99 |        1   |          199   |                1 |
| qwen3.5:4b   |        4   | L4          | L4        | L4            | L4                  | L2                      |          0.92 |        1    |        2   |          108.9 |                0 |
| gemma4:e4b   |        4.5 | L4          | L4        | L4            | L4                  | L4                      |          0.95 |        1    |        1.5 |          137.1 |                0 |
| qwen3.5:9b   |        9   | L4          | L4        | L4            | L4                  | L4                      |          0.99 |        1    |        2.7 |           73.4 |                1 |
| gemma4:12b   |       12   | L4          | L4        | L4            | L4                  | L3                      |          0.95 |        1    |        2.5 |           75   |                0 |
| gemma4:26b   |       25.2 | L4          | L4        | L4            | L4                  | L4                      |          0.98 |        1    |        2.9 |          102.5 |                0 |
| qwen3.5:27b  |       27   | L4          | L4        | L4            | L4                  | L4                      |          0.99 |        1    |       10.8 |           25.5 |                0 |
| qwen3.8:27b  |       27   | L4          | L4        | L4            | L4                  | L4                      |          0.99 |        1    |        7.7 |           36.9 |                0 |
| gemma4:31b   |       30.7 | L4          | L4        | L4            | L4                  | L3                      |          0.97 |        1    |        8.5 |           21.1 |                0 |

![heatmap](boundary_heatmap.png)

## Accuracy table

| config       |   knowledge_L1 |   knowledge_L2 |   knowledge_L3 |   knowledge_L4 |   concept_L1 |   concept_L2 |   concept_L3 |   concept_L4 |   calculation_L1 |   calculation_L2 |   calculation_L3 |   calculation_L4 |   applied_reasoning_L1 |   applied_reasoning_L2 |   applied_reasoning_L3 |   applied_reasoning_L4 |   instruction_following_L1 |   instruction_following_L2 |   instruction_following_L3 |   instruction_following_L4 |
|:-------------|---------------:|---------------:|---------------:|---------------:|-------------:|-------------:|-------------:|-------------:|-----------------:|-----------------:|-----------------:|-----------------:|-----------------------:|-----------------------:|-----------------------:|-----------------------:|---------------------------:|---------------------------:|---------------------------:|---------------------------:|
| qwen3.5:0.8b |              1 |            0.6 |            0.6 |            0.2 |          0.8 |          0.8 |          0.8 |          0.8 |              1   |              0.8 |              0.2 |              0   |                      1 |                    0.8 |                    0.8 |                    0.4 |                          1 |                        0.6 |                        0.8 |                        0.8 |
| qwen3.5:2b   |              1 |            1   |            0.8 |            0.4 |          1   |          0.8 |          0.8 |          0.6 |              1   |              0.8 |              0.8 |              0.6 |                      1 |                    1   |                    0.8 |                    0.4 |                          1 |                        0.8 |                        0.8 |                        0.6 |
| gemma4:e2b   |              1 |            0.8 |            0.8 |            0.6 |          1   |          1   |          0.8 |          1   |              0.8 |              1   |              1   |              0.6 |                      1 |                    1   |                    0.8 |                    0.6 |                          1 |                        1   |                        0.8 |                        0.8 |
| qwen3.5:4b   |              1 |            1   |            0.8 |            0.8 |          1   |          1   |          1   |          1   |              1   |              1   |              0.8 |              0.8 |                      1 |                    1   |                    1   |                    1   |                          1 |                        0.8 |                        0.6 |                        0.8 |
| gemma4:e4b   |              1 |            1   |            1   |            0.8 |          1   |          1   |          1   |          1   |              1   |              1   |              1   |              1   |                      1 |                    1   |                    0.8 |                    0.8 |                          1 |                        1   |                        0.8 |                        0.8 |
| qwen3.5:9b   |              1 |            1   |            1   |            0.8 |          1   |          1   |          1   |          1   |              1   |              1   |              1   |              1   |                      1 |                    1   |                    1   |                    1   |                          1 |                        1   |                        1   |                        1   |
| gemma4:12b   |              1 |            1   |            1   |            0.8 |          1   |          1   |          1   |          1   |              1   |              1   |              1   |              1   |                      1 |                    1   |                    0.8 |                    1   |                          1 |                        1   |                        0.8 |                        0.6 |
| gemma4:26b   |              1 |            1   |            1   |            1   |          1   |          1   |          1   |          1   |              1   |              1   |              1   |              1   |                      1 |                    1   |                    1   |                    1   |                          1 |                        1   |                        0.8 |                        0.8 |
| qwen3.5:27b  |              1 |            1   |            1   |            1   |          1   |          1   |          1   |          1   |              1   |              1   |              1   |              1   |                      1 |                    1   |                    1   |                    1   |                          1 |                        0.8 |                        1   |                        1   |
| qwen3.8:27b  |              1 |            1   |            1   |            1   |          1   |          1   |          1   |          1   |              1   |              1   |              1   |              1   |                      1 |                    1   |                    1   |                    1   |                          1 |                        1   |                        0.8 |                        1   |
| gemma4:31b   |              1 |            1   |            1   |            1   |          1   |          1   |          1   |          1   |              1   |              1   |              1   |              1   |                      1 |                    1   |                    1   |                    1   |                          1 |                        1   |                        0.8 |                        0.6 |

## Chinese vs English (same 10 questions)

| config       |   english_acc |   chinese_acc |   n_pairs |
|:-------------|--------------:|--------------:|----------:|
| qwen3.5:0.8b |           0.6 |           0.6 |        10 |
| qwen3.5:2b   |           1   |           0.8 |        10 |
| gemma4:e2b   |           0.9 |           1   |        10 |
| qwen3.5:4b   |           1   |           1   |        10 |
| gemma4:e4b   |           1   |           1   |        10 |
| qwen3.5:9b   |           1   |           1   |        10 |
| gemma4:12b   |           1   |           1   |        10 |
| gemma4:26b   |           1   |           1   |        10 |
| qwen3.5:27b  |           1   |           1   |        10 |
| qwen3.8:27b  |           1   |           1   |        10 |
| gemma4:31b   |           1   |           1   |        10 |

## Wrong answers (for manual inspection)

| config | id | type | detail |
|---|---|---|---|
| gemma4:12b | R3-5 | open | manual |
| gemma4:12b | I3-3 | rule | invalid JSON (or extra text / code fences) |
| gemma4:12b | I4-3 | rule | invalid JSON (or extra text / code fences) |
| gemma4:12b | I4-5 | rule | 67 words > 65 |
| gemma4:12b | K4-1 | short | got 'Zehni, 2017' |
| gemma4:26b | I3-3 | rule | invalid JSON (or extra text / code fences) |
| gemma4:26b | I4-3 | rule | invalid JSON (or extra text / code fences) |
| gemma4:31b | I3-3 | rule | invalid JSON (or extra text / code fences) |
| gemma4:31b | I4-3 | rule | invalid JSON (or extra text / code fences) |
| gemma4:31b | I4-4 | rule | not mainly Chinese; English words: ['agreement', 'agreement'] |
| gemma4:e2b | R3-5 | open | manual |
| gemma4:e2b | R4-1 | mcq | got C |
| gemma4:e2b | R4-4 | mcq | got A |
| gemma4:e2b | C1-2 | numeric | no number |
| gemma4:e2b | C4-3 | numeric | got 10.0 |
| gemma4:e2b | C4-4 | numeric | got 0.7272727272727273 |
| gemma4:e2b | U3-1 | mcq | got B |
| gemma4:e2b | I3-3 | rule | invalid JSON (or extra text / code fences) |
| gemma4:e2b | I4-3 | rule | invalid JSON (or extra text / code fences) |
| gemma4:e2b | K2-4 | mcq | got B |
| gemma4:e2b | K3-4 | numeric | got 0.0 |
| gemma4:e2b | K4-1 | short | got 'Please provide the specific paper for accurate information.' |
| gemma4:e2b | K4-4 | open | manual |
| gemma4:e4b | R3-5 | open | manual |
| gemma4:e4b | R4-5 | open | manual |
| gemma4:e4b | I3-3 | rule | invalid JSON (or extra text / code fences) |
| gemma4:e4b | I4-3 | rule | invalid JSON (or extra text / code fences) |
| gemma4:e4b | K4-4 | open | manual |
| qwen3.5:0.8b | R2-1 | mcq | got B |
| qwen3.5:0.8b | R3-5 | open | manual |
| qwen3.5:0.8b | R4-2 | mcq | got B |
| qwen3.5:0.8b | R4-4 | mcq | got C |
| qwen3.5:0.8b | R4-5 | open | manual |
| qwen3.5:0.8b | C2-4 | numeric | got 0.053 |
| qwen3.5:0.8b | C3-1 | numeric | got 0.0105 |
| qwen3.5:0.8b | C3-2 | numeric | got 0.0014 |
| qwen3.5:0.8b | C3-4 | numeric | got 2.0 |
| qwen3.5:0.8b | C3-5 | numeric | got 0.89 |
| qwen3.5:0.8b | C4-1 | numeric | got 0.33 |
| qwen3.5:0.8b | C4-2 | numeric | got 246.0 |
| qwen3.5:0.8b | C4-3 | numeric | got 1.0 |
| qwen3.5:0.8b | C4-4 | numeric | got 0.0073 |
| qwen3.5:0.8b | C4-5 | numeric | got 40000.0 |
| qwen3.5:0.8b | U1-1 | mcq | got None |
| qwen3.5:0.8b | U2-4 | mcq | got None |
| qwen3.5:0.8b | U3-1 | mcq | got B |
| qwen3.5:0.8b | U4-5 | open | manual |
| qwen3.5:0.8b | I2-2 | rule | 31 words > 29 |
| qwen3.5:0.8b | I2-3 | rule | uses word 'standards' |
| qwen3.5:0.8b | I3-3 | rule | sensitive=NOT_SENSITIVE |
| qwen3.5:0.8b | I4-3 | rule | wrong number |
| qwen3.5:0.8b | K2-4 | mcq | got C |
| qwen3.5:0.8b | K2-5 | short | got 'PHI' |
| qwen3.5:0.8b | K3-3 | short | got 'Male' |
| qwen3.5:0.8b | K3-4 | numeric | got 2013.0 |
| qwen3.5:0.8b | K4-1 | short | got 'Yossi Ben-David, 2015' |
| qwen3.5:0.8b | K4-2 | open | manual |
| qwen3.5:0.8b | K4-3 | mcq | got A |
| qwen3.5:0.8b | K4-4 | open | manual |
| qwen3.5:27b | I2-3 | rule | uses word 'standard' |
| qwen3.5:2b | R3-5 | open | manual |
| qwen3.5:2b | R4-1 | mcq | got B |
| qwen3.5:2b | R4-2 | mcq | got B |
| qwen3.5:2b | R4-5 | open | manual |
| qwen3.5:2b | C2-4 | numeric | got 0.7576 |
| qwen3.5:2b | C3-2 | numeric | got 1.01 |
| qwen3.5:2b | C4-2 | numeric | got 108.0 |
| qwen3.5:2b | C4-3 | numeric | got 1.0 |
| qwen3.5:2b | U2-3 | mcq | got None |
| qwen3.5:2b | U3-3 | mcq | got B |
| qwen3.5:2b | U4-4 | mcq | got B |
| qwen3.5:2b | U4-5 | open | manual |
| qwen3.5:2b | I2-3 | rule | uses word 'standard' |
| qwen3.5:2b | I3-3 | rule | sensitive=NOT_SENSITIVE |
| qwen3.5:2b | I4-1 | rule | missing '?'; contains '0.33' |
| qwen3.5:2b | I4-4 | rule | English words: ['alpha', 'alpha'] |
| qwen3.5:2b | K3-4 | numeric | got 1988.0 |
| qwen3.5:2b | K4-1 | short | got 'Zhou, 2017' |
| qwen3.5:2b | K4-2 | open | manual |
| qwen3.5:2b | K4-5 | mcq | got C |
| qwen3.5:4b | C3-2 | numeric | got 0.35 |
| qwen3.5:4b | C4-3 | numeric | got 0.9091 |
| qwen3.5:4b | I2-2 | rule | 30 words > 29 |
| qwen3.5:4b | I3-3 | rule | sensitive=NOT_SENSITIVE |
| qwen3.5:4b | I3-4 | rule | contains digits |
| qwen3.5:4b | I4-1 | rule | missing '?' |
| qwen3.5:4b | K3-4 | numeric | got 2003.0 |
| qwen3.5:4b | K4-1 | short | got 'Battaglia, 2018' |
| qwen3.5:9b | K4-1 | short | got 'Springenberg, 2016' |
| qwen3.8:27b | I3-3 | rule | sensitive=NOT_SENSITIVE |