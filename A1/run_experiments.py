import token_ring
import json
import statistics
import time
import sys

def summarize(stats):
    total_rounds = sum(s['rounds'] for s in stats)
    total_fireworks = sum(s['fireworks'] for s in stats)
    all_durations = [t for s in stats for t in s['round_times']]

    if not all_durations:
        return {
            'total_rounds': 0,
            'total_fireworks': 0,
            'min_round_duration': 0,
            'avg_round_duration': 0,
            'max_round_duration': 0
        }

    min_dur = min(all_durations)
    max_dur = max(all_durations)
    avg_dur = statistics.mean(all_durations)

    return {
        'total_rounds': total_rounds,
        'total_fireworks': total_fireworks,
        'min_round_duration': min_dur,
        'avg_round_duration': avg_dur,
        'max_round_duration': max_dur
    }

def main():
    p = 0.8
    k = 5
    max_n = 1
    results = []
    MAX_RUNTIME = 30  # seconds

    print("n,total_rounds,total_fireworks,min_dur,avg_dur,max_dur")
    for exp in range(1, 12):  # up to 2^11 = 2048
        n = 2 ** exp
        try:
            print(f"\n▶ Starting run for n={n}...")
            start = time.time()
            stats = token_ring.run_ring(n, p, k)
            end = time.time()

            if end - start > MAX_RUNTIME:
                print(f"{n},FAIL,Exceeded max runtime of {MAX_RUNTIME}s")
                break

            summary = summarize(stats)
            if summary['total_rounds'] == 0:
                print(f"{n},FAIL,No rounds completed")
                break

            summary['total_time'] = end - start
            results.append((n, summary))
            print(f"{n},{summary['total_rounds']},{summary['total_fireworks']},"
                  f"{summary['min_round_duration']:.4f},{summary['avg_round_duration']:.4f},"
                  f"{summary['max_round_duration']:.4f}")
            max_n = n
        except Exception as e:
            print(f"{n},FAIL,{str(e)}")
            break

    print(f"\n✅ Maximum working n: {max_n}")
    return results

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\nAborted by user.")
        sys.exit(0)
