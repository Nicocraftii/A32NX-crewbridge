from backend.simconnect_mobiflight import SimConnectMobiFlight
from backend.mobiflight_variable_requests import MobiFlightVariableRequests
import time
import json
import sqlite3
import sys
import threading
from queue import Queue, Empty
from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError
from typing import Dict, List
import signal


class SignalHandler:
    """Handle Ctrl+C gracefully"""
    def __init__(self):
        self.should_exit = False
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        self.should_exit = True
        print("\n\nInterrupted! Exiting gracefully...")


class ReliableFastLVARReader:
    def __init__(self, max_workers=15):
        self.sm = SimConnectMobiFlight()
        self.vr = MobiFlightVariableRequests(self.sm)
        self.max_workers = max_workers
        self.signal_handler = SignalHandler()
        print(f"ReliableFast Reader initialized with {max_workers} workers")
    
    def read_var_reliable(self, var_name: str) -> float:
        """Reliable single variable read with proper error handling"""
        try:
            if not var_name.startswith("(L:"):
                var_name = f"(L:{var_name})"
            
            # Use reasonable timeout
            value = self.vr.get(var_name, timeout=0.25)
            return value if value is not None else 0.0
        except Exception as e:
            return 0.0
    
    def read_all_reliable_fast(self, var_names: List[str]) -> Dict[str, float]:
        """Reliable and fast reading with backpressure control"""
        total = len(var_names)
        print(f"Reading {total} LVARs reliably...")
        
        results = {}
        completed = 0
        failed = 0
        start_time = time.time()
        
        # Use ThreadPoolExecutor with proper backpressure
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all tasks but control the flow
            future_to_var = {}
            batch_size = 50  # Submit in batches
            
            for i in range(0, total, batch_size):
                if self.signal_handler.should_exit:
                    print("\nInterrupted by user")
                    break
                
                batch = var_names[i:min(i + batch_size, total)]
                
                # Submit batch
                for var in batch:
                    future = executor.submit(self.read_var_reliable, var)
                    future_to_var[future] = var
                
                # Process completed futures from this batch
                batch_start_time = time.time()
                for future in as_completed(list(future_to_var.keys()), timeout=5.0):
                    if self.signal_handler.should_exit:
                        break
                    
                    var = future_to_var.pop(future)
                    try:
                        value = future.result(timeout=0.1)
                        results[var] = value
                        completed += 1
                    except Exception as e:
                        results[var] = 0.0
                        failed += 1
                    
                    # Progress update
                    if completed % 20 == 0:
                        elapsed = time.time() - start_time
                        rate = completed / elapsed if elapsed > 0 else 0
                        print(f"\r  Progress: {completed}/{total} ({completed/total*100:.1f}%) - {rate:.1f} vars/sec - Failed: {failed}", end="")
                
                # Small delay between batches
                if i + batch_size < total and not self.signal_handler.should_exit:
                    time.sleep(0.02)
        
        elapsed = time.time() - start_time
        print(f"\r  Progress: {completed}/{total} (100.0%) - {completed/elapsed:.1f} vars/sec - Failed: {failed}")
        
        return results
    
    def read_all_simple_fast(self, var_names: List[str]) -> Dict[str, float]:
        """Simple but fast approach - works well for SimConnect"""
        total = len(var_names)
        print(f"Reading {total} LVARs (simple fast method)...")
        
        results = {}
        start_time = time.time()
        
        # Clear old variables first
        self.vr.clear_sim_variables()
        time.sleep(0.5)
        
        # Read in small concurrent batches
        batch_size = 30
        num_batches = (total + batch_size - 1) // batch_size
        
        for batch_idx in range(num_batches):
            if self.signal_handler.should_exit:
                break
            
            batch_start = batch_idx * batch_size
            batch_end = min(batch_start + batch_size, total)
            batch = var_names[batch_start:batch_end]
            
            print(f"  Batch {batch_idx + 1}/{num_batches} ({len(batch)} vars)")
            
            # Read this batch with limited concurrency
            batch_results = self._read_batch_concurrent(batch)
            results.update(batch_results)
            
            # Progress
            processed = batch_end
            elapsed = time.time() - start_time
            rate = processed / elapsed if elapsed > 0 else 0
            print(f"    Progress: {processed}/{total} - {rate:.1f} vars/sec")
        
        return results
    
    def _read_batch_concurrent(self, batch: List[str]) -> Dict[str, float]:
        """Read a batch concurrently with controlled concurrency"""
        results = {}
        
        # Use ThreadPoolExecutor with limited workers
        with ThreadPoolExecutor(max_workers=min(8, len(batch))) as executor:
            future_to_var = {executor.submit(self.read_var_reliable, var): var for var in batch}
            
            for future in as_completed(future_to_var, timeout=3.0):
                var = future_to_var[future]
                try:
                    results[var] = future.result(timeout=0.1)
                except:
                    results[var] = 0.0
        
        return results


def read_lvars_reliable_fast(lvars_file: str = 'lvars.json', db_file: str = 'sync.db', 
                            max_workers: int = 15, method: str = 'simple'):
    """Reliable and fast LVAR reading"""
    
    print("="*60)
    print("MSFS LVAR Reader - RELIABLE & FAST Edition")
    print("="*60)
    
    # Load LVARs
    with open(lvars_file, 'r') as f:
        data = json.load(f)
    
    var_names = list(data.keys())
    print(f"Found {len(var_names)} LVARs")
    
    # Create reader
    reader = ReliableFastLVARReader(max_workers=max_workers)
    
    # Read all variables
    print(f"\nStarting read with {max_workers} workers ({method} method)...")
    start_time = time.time()
    
    if method == 'simple':
        results = reader.read_all_simple_fast(var_names)
    else:
        results = reader.read_all_reliable_fast(var_names)
    
    elapsed = time.time() - start_time
    
    # Stats
    non_zero = sum(1 for v in results.values() if v != 0.0)
    
    print(f"\n{'='*50}")
    print(f"READ COMPLETE!")
    print(f"Time: {elapsed:.2f} seconds")
    print(f"Speed: {len(results)/elapsed:.1f} vars/second")
    print(f"Non-zero values: {non_zero}/{len(results)}")
    print(f"{'='*50}")
    
    # Save to database
    print("\nSaving to database...")
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS simvars(
        var_key TEXT PRIMARY KEY, 
        value NUMERIC, 
        timestamp REAL
    )
    """)
    
    cursor.execute('DELETE FROM simvars;')
    
    current_time = time.time()
    batch_data = [(var, results.get(var, 0.0), current_time) for var in var_names]
    
    cursor.executemany(
        'INSERT OR REPLACE INTO simvars (var_key, value, timestamp) VALUES (?, ?, ?)',
        batch_data
    )
    
    conn.commit()
    
    # Verify
    cursor.execute('SELECT COUNT(*) FROM simvars')
    count = cursor.fetchone()[0]
    
    print(f"Saved {count} values to {db_file}")
    
    # Show sample
    print("\nSample values (first 5):")
    for i, var in enumerate(var_names[:5]):
        print(f"  {var}: {results.get(var, 0.0)}")
    
    conn.close()
    
    return results, elapsed


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Reliable Fast LVAR Reader')
    parser.add_argument('--workers', type=int, default=15, help='Number of worker threads')
    parser.add_argument('--method', choices=['simple', 'reliable'], default='simple', help='Reading method')
    parser.add_argument('--lvars-file', default='lvars.json', help='LVARs JSON file')
    parser.add_argument('--db-file', default='sync_reliable.db', help='Database file')
    parser.add_argument('--test', action='store_true', help='Run a quick test first')
    
    args = parser.parse_args()
    
    if args.test:
        # Quick test first
        print("Running quick test...")
        test_vars = [
            "A32NX_IS_READY",
            "A32NX_FLAPS_HANDLE_INDEX",
            "A32NX_PARK_BRAKE_LEVER_POS",
            "A32NX_AUTOBRAKES_ARMED_MODE",
            "A32NX_FIRE_BUTTON_ENG1"
        ]
        
        reader = ReliableFastLVARReader(max_workers=args.workers)
        
        start = time.time()
        for var in test_vars:
            value = reader.read_var_reliable(var)
            print(f"  {var}: {value}")
        
        test_time = time.time() - start
        print(f"\nTest completed in {test_time:.2f}s")
        print(f"Estimated time for 476 vars: {(test_time/5)*476:.1f}s")
        
        proceed = input("\nProceed with full read? (y/n): ")
        if proceed.lower() != 'y':
            return
    
    try:
        results, elapsed = read_lvars_reliable_fast(
            lvars_file=args.lvars_file,
            db_file=args.db_file,
            max_workers=args.workers,
            method=args.method
        )
        
        print(f"\n{'='*60}")
        print(f"SUCCESS!")
        print(f"Performance: {len(results)/elapsed:.1f} vars/second")
        print(f"{'='*60}")
        
    except KeyboardInterrupt:
        print("\n\nInterrupted by user. Exiting...")
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()