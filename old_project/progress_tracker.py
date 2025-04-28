import os
import json
import time
import shutil
import asyncio
from typing import List, Dict, Any, Callable, Optional
from datetime import datetime
from dataclasses import dataclass, field
from collections import defaultdict
from datasets import Dataset, load_dataset, load_from_disk
from tqdm import tqdm

@dataclass
class ProgressTracker:
    """
    Tracks progress and statistics during benchmark runs.
    
    Attributes:
        total_examples: Total number of examples to process
        config: BenchmarkConfig instance for accessing settings
        results: List of processed results
        start_time: Timestamp when tracking started
    """
    total_examples: int
    config: Any
    results: List[Dict] = field(default_factory=list)
    start_time: datetime = field(default_factory=datetime.now)
    
    def _has_field(self, data_list: List[Dict], field_name: str) -> bool:
        """Check if any dictionary in the list contains the specified field"""
        return any(field_name in item for item in data_list)
    
    def _save_progress_stats(self, stats: str) -> None:
        """Save progress statistics to a log file"""
        if not self.config.produce_statistics:
            return
            
        os.makedirs("results", exist_ok=True)
        stats_file = os.path.join("results", f"progress_stats_{self.start_time.strftime('%Y%m%d_%H%M%S')}.log")
        with open(stats_file, 'a') as f:
            f.write(f"{datetime.now().isoformat()}: {stats}\n")

    def add_result(self, results: List[Dict]) -> None:
        """Add a list of results to the tracker and update progress"""
        if results:
            self.results.extend(results)
            # Count only statistics entries for checkpoints
            stats_count = len([r for r in self.results if r.get('data_type') == 'statistics'])
            if stats_count > 0 and stats_count % self.config.stats_update_freq == 0:
                self.print_progress()
                self._save_progress_stats(f"Checkpoint at {stats_count} examples")
                # Save intermediate results
                self.save_results()
    
    def _calculate_statistics(self, entries: List[Dict]) -> Dict:
        """Calculate statistics from a list of statistics entries"""
        if not entries:
            return {}
            
        total = len(entries)
        stats = {}
        
        # Basic statistics
        stats['total'] = total
        successfully_processed = sum(1 for r in entries if r.get('example_processed_successfully', False))
        stats['successfully_processed'] = successfully_processed
        stats['processing_success_rate'] = (successfully_processed / total * 100) if total > 0 else 0
        
        # Test verification statistics (for programmer_test benchmarks)
        test_entries = [r for r in entries if 'test_passed' in r or 'verified_correct' in r]
        if test_entries:
            # Count test statistics
            test_passed_count = sum(1 for r in test_entries if r.get('test_passed') is not None and any(r.get('test_passed', [])))
            verified_correct_count = sum(1 for r in test_entries if r.get('verified_correct') is not None and any(r.get('verified_correct', [])))
            
            stats['test_passed_count'] = test_passed_count
            stats['test_passed_rate'] = (test_passed_count / len(test_entries) * 100) if test_entries else 0
            stats['verified_correct_count'] = verified_correct_count
            stats['verified_correct_rate'] = (verified_correct_count / len(test_entries) * 100) if test_entries else 0
            
            # Track improvement from testing
            initial_correct_count = sum(1 for r in test_entries if r.get('initial_majority_correct', False))
            final_correct_count = sum(1 for r in test_entries if r.get('final_majority_correct', False))
            
            stats['initial_correct_count'] = initial_correct_count
            stats['final_correct_count'] = final_correct_count
            stats['testing_improvement'] = final_correct_count - initial_correct_count
            stats['testing_improvement_rate'] = ((final_correct_count - initial_correct_count) / len(test_entries) * 100) if test_entries else 0
        
        # First pass: calculate total correct solutions and at_least_one
        at_least_one = 0
        total_correct = 0
        initial_most_common_correct = 0
        final_most_common_correct = 0
        
        # Track per-problem correct counts for above-average calculation
        problem_correct_counts = []
        
        for r in entries:
            # Process initial solutions
            initial_matches = None
            if 'initial_correctness' in r and isinstance(r['initial_correctness'], list):
                initial_matches = r['initial_correctness']
            elif 'is_correct_list' in r and isinstance(r['is_correct_list'], list):
                # Fall back to original format
                initial_matches = r['is_correct_list']
            else:
                # Create a single-item list for benchmarks that only report overall correctness
                initial_matches = [r.get('is_correct', False)] if 'is_correct' in r else []
                
            if initial_matches:
                # Check if any verdict matches
                matches_count = sum(1 for match in initial_matches if match)
                if matches_count > 0:
                    at_least_one += 1
                total_correct += matches_count
                
                # Store the count of correct solutions for this problem
                problem_correct_counts.append(matches_count)
            
            # Process final solutions
            final_matches = None
            if 'final_correctness' in r and isinstance(r['final_correctness'], list):
                final_matches = r['final_correctness']
            elif not 'final_correctness' in r and initial_matches:
                # If no final solutions, use initial for backward compatibility
                # This will be handled in the second pass
                pass
                    
            # Check most common verdict - separate initial and final
            if r.get('is_most_common_correct', False):
                # For traditional benchmark (backward compatibility)
                initial_most_common_correct += 1
                # Only use this for final if no explicit filtered_is_most_common_correct field
                if 'filtered_is_most_common_correct' not in r:
                    final_most_common_correct += 1
            else:
                # For benchmarks with separate initial and final majority
                if r.get('initial_is_most_common_correct', False):
                    initial_most_common_correct += 1
                if r.get('filtered_is_most_common_correct', False):
                    final_most_common_correct += 1
                elif r.get('final_majority_correct', False):
                    final_most_common_correct += 1
                # For hybrid benchmark
                if r.get('most_common_correct', False):
                    initial_most_common_correct += 1
                    final_most_common_correct += 1
                
        # Calculate average correct solutions per problem
        stats['at_least_one'] = at_least_one
        stats['avg_correct'] = total_correct / total if total > 0 else 0
        
        # Second pass: calculate above-average statistics
        initial_above_avg = 0
        final_above_avg = 0
        
        # Calculate how many problems have above average correct solutions
        # Above average should mean the problem has more correct solutions than the average
        # AND at least one correct solution
        avg_correct = stats.get('avg_correct', 0)
        
        # Only count problems with at least one correct solution
        valid_counts = [count for count in problem_correct_counts if count > 0]
        
        # Calculate a new average based only on problems with at least one correct solution
        if valid_counts:
            valid_avg = sum(valid_counts) / len(valid_counts)
            
            # Count problems that have more correct solutions than the valid average
            for count in problem_correct_counts:
                if count > 0 and count > valid_avg:
                    initial_above_avg += 1
            
            # For final counts, use separate tracking if available
            for r in entries:
                # Check if this entry has filtered_correct_solutions field
                if 'filtered_correct_solutions' in r and r.get('filtered_correct_solutions', 0) > 0:
                    if r.get('filtered_correct_solutions', 0) > valid_avg:
                        final_above_avg += 1
                # Fall back to initial counts if no filtered data
                elif not any('filtered_correct_solutions' in entry for entry in entries):
                    if r.get('correct_solutions', 0) > 0 and r.get('correct_solutions', 0) > valid_avg:
                        final_above_avg += 1
        else:
            # If no problems have correct solutions, none are above average
            initial_above_avg = 0
            final_above_avg = 0
        
        stats['initial_above_avg'] = initial_above_avg
        stats['final_above_avg'] = final_above_avg
        stats['initial_most_common_correct'] = initial_most_common_correct
        stats['final_most_common_correct'] = final_most_common_correct
        
        # Tutor solution benchmark statistics
        tutor_entries = [r for r in entries if 'initial_correctness' in r or 'final_correctness' in r]
        if tutor_entries:
            # Track best-of statistics
            all_initial_correctness = []
            for r in tutor_entries:
                if 'initial_correctness' in r and isinstance(r['initial_correctness'], list):
                    all_initial_correctness.extend(r['initial_correctness'])
            
            if all_initial_correctness:
                stats['total_initial_solutions'] = len(all_initial_correctness)
                stats['total_initial_correct'] = sum(1 for x in all_initial_correctness if x)
                stats['overall_initial_success_rate'] = (stats['total_initial_correct'] / stats['total_initial_solutions'] * 100) if stats['total_initial_solutions'] > 0 else 0
                
                # Calculate how many examples had at least one correct solution
                examples_with_at_least_one_correct = sum(1 for r in tutor_entries if r.get('initial_correctness') and any(r['initial_correctness']))
                stats['examples_with_at_least_one_correct'] = examples_with_at_least_one_correct
                stats['examples_with_at_least_one_correct_rate'] = (examples_with_at_least_one_correct / total * 100) if total > 0 else 0
            
            # Track majority vote statistics
            initial_majority_correct_count = sum(1 for r in tutor_entries if r.get('initial_majority_correct', False))
            stats['initial_majority_correct_count'] = initial_majority_correct_count
            stats['initial_majority_correct_rate'] = (initial_majority_correct_count / total * 100) if total > 0 else 0
            
            # Track final solution statistics
            all_final_correctness = []
            for r in tutor_entries:
                if 'final_correctness' in r and isinstance(r['final_correctness'], list):
                    all_final_correctness.extend(r['final_correctness'])
            
            if all_final_correctness:
                stats['total_final_solutions'] = len(all_final_correctness)
                stats['total_final_correct'] = sum(1 for x in all_final_correctness if x)
                stats['overall_final_success_rate'] = (stats['total_final_correct'] / stats['total_final_solutions'] * 100) if stats['total_final_solutions'] > 0 else 0
            
            # Track final majority vote statistics
            final_majority_correct_count = sum(1 for r in tutor_entries if r.get('final_majority_correct', False))
            stats['final_majority_correct_count'] = final_majority_correct_count
            stats['final_majority_correct_rate'] = (final_majority_correct_count / total * 100) if total > 0 else 0
            
            # Track improvement statistics
            majority_vote_improved_count = sum(1 for r in tutor_entries if r.get('majority_vote_improved', False))
            stats['majority_vote_improved_count'] = majority_vote_improved_count
            stats['majority_vote_improved_rate'] = (majority_vote_improved_count / total * 100) if total > 0 else 0
            
            majority_vote_worsened_count = sum(1 for r in tutor_entries if r.get('majority_vote_worsened', False))
            stats['majority_vote_worsened_count'] = majority_vote_worsened_count
            stats['majority_vote_worsened_rate'] = (majority_vote_worsened_count / total * 100) if total > 0 else 0
            
            success_rate_improved_count = sum(1 for r in tutor_entries if r.get('success_rate_improved', False))
            stats['success_rate_improved_count'] = success_rate_improved_count
            stats['success_rate_improved_rate'] = (success_rate_improved_count / total * 100) if total > 0 else 0
            
            # Count solutions improved or worsened by tutor
            solutions_improved = 0
            solutions_worsened = 0
            
            # Track quality improvements
            initial_quality_sum = 0
            final_quality_sum = 0
            quality_improved_count = 0
            quality_worsened_count = 0
            
            for r in tutor_entries:
                initial_correct = r.get('initial_solution_correct', False)
                final_correct = r.get('final_solution_correct', False)
                
                # Binary correct/incorrect tracking
                if not initial_correct and final_correct:
                    solutions_improved += 1
                elif initial_correct and not final_correct:
                    solutions_worsened += 1
                
                # Quality tracking (how close to correct answer)
                initial_quality = r.get('initial_solution_quality')
                final_quality = r.get('final_solution_quality')
                
                if initial_quality is not None and final_quality is not None:
                    # For numeric answers, we can compare how close they are to the correct answer
                    # Lower is better (closer to correct)
                    if isinstance(initial_quality, (int, float)) and isinstance(final_quality, (int, float)):
                        initial_quality_sum += abs(initial_quality)
                        final_quality_sum += abs(final_quality)
                        
                        # Count cases where quality improved or worsened
                        if abs(final_quality) < abs(initial_quality):
                            quality_improved_count += 1
                        elif abs(final_quality) > abs(initial_quality):
                            quality_worsened_count += 1
            
            # Store binary improvement/worsening stats
            stats['solutions_improved_count'] = solutions_improved
            stats['solutions_improved_rate'] = (solutions_improved / total * 100) if total > 0 else 0
            stats['solutions_worsened_count'] = solutions_worsened
            stats['solutions_worsened_rate'] = (solutions_worsened / total * 100) if total > 0 else 0
            
            # Store quality improvement stats
            valid_quality_entries = sum(1 for r in tutor_entries if 
                                      r.get('initial_solution_quality') is not None and 
                                      r.get('final_solution_quality') is not None and
                                      isinstance(r.get('initial_solution_quality'), (int, float)) and
                                      isinstance(r.get('final_solution_quality'), (int, float)))
            
            if valid_quality_entries > 0:
                stats['valid_quality_entries'] = valid_quality_entries
                stats['initial_avg_quality'] = initial_quality_sum / valid_quality_entries
                stats['final_avg_quality'] = final_quality_sum / valid_quality_entries
                stats['quality_improved_count'] = quality_improved_count
                stats['quality_improved_rate'] = (quality_improved_count / valid_quality_entries * 100)
                stats['quality_worsened_count'] = quality_worsened_count
                stats['quality_worsened_rate'] = (quality_worsened_count / valid_quality_entries * 100)
            
            # Track solution sources
            from collections import Counter
            solution_sources_counter = Counter()
            for r in tutor_entries:
                if 'solution_sources' in r and isinstance(r['solution_sources'], list):
                    solution_sources_counter.update(r['solution_sources'])
                elif 'solution_source' in r:
                    solution_sources_counter[r.get('solution_source', 'unknown')] += 1
            
            stats['solution_sources'] = dict(solution_sources_counter)
        
        # Judge statistics
        judge_entries = [r for r in entries if r.get('judge_accuracy') is not None]
        if judge_entries:
            stats['judge_decisions'] = len(judge_entries)
            stats['avg_judge_accuracy'] = sum(r['judge_accuracy'] for r in judge_entries) / len(judge_entries)
        
        # Step benchmark statistics from regular statistics entries
        step_entries = [r for r in entries if 'wrong_steps_found' in r or 'wrong_step_found' in r]
        if step_entries:
            # Wrong step statistics
            wrong_steps_found = sum(r.get('wrong_steps_found', 0) for r in step_entries)
            # Also count individual wrong_step_found entries (boolean)
            wrong_steps_found += sum(1 for r in step_entries if r.get('wrong_step_found', False) and 'wrong_steps_found' not in r)
            stats['wrong_steps_found'] = wrong_steps_found
            
            # Position statistics
            position_values = [r.get('avg_wrong_step_position', 0) for r in step_entries if 'avg_wrong_step_position' in r]
            # Also include individual wrong_step_index values
            position_values.extend([r.get('wrong_step_index', 0) / r.get('total_steps', 1) 
                                  for r in step_entries 
                                  if 'wrong_step_index' in r and r.get('wrong_step_index', -1) >= 0 and 'total_steps' in r and r.get('total_steps', 0) > 0])
            if position_values:
                stats['avg_wrong_step_position'] = sum(position_values) / len(position_values)
            
            # Combine position distributions
            from collections import Counter
            position_dist = Counter()
            for r in step_entries:
                if 'position_distribution' in r:
                    position_dist.update(r['position_distribution'])
                elif 'position_category' in r:
                    position_dist[r['position_category']] = position_dist.get(r['position_category'], 0) + 1
            stats['position_distribution'] = dict(position_dist)
            
            # Recovery statistics
            recovery_rates = [r.get('recovery_success_rate', 0) for r in step_entries if 'recovery_success_rate' in r]
            if recovery_rates:
                stats['recovery_success_rate'] = sum(recovery_rates) / len(recovery_rates)
            
            # Completion score statistics
            completion_scores = [r.get('avg_completion_score', 0) for r in step_entries if 'avg_completion_score' in r]
            completion_scores.extend([r.get('completion_score', 0) for r in step_entries if 'completion_score' in r and 'avg_completion_score' not in r])
            if completion_scores:
                stats['avg_completion_score'] = sum(completion_scores) / len(completion_scores)
            
            # Unsalvageable statistics
            unsalvageable_counts = [r.get('unsalvageable_solutions', 0) for r in step_entries if 'unsalvageable_solutions' in r]
            # Also count individual unsalvageable entries (boolean)
            unsalvageable_counts.append(sum(1 for r in step_entries if r.get('unsalvageable', False) and 'unsalvageable_solutions' not in r))
            if unsalvageable_counts:
                stats['unsalvageable_solutions'] = sum(unsalvageable_counts)
                
            # Combine unsalvageable reasons
            unsalvageable_reasons = {}
            for r in step_entries:
                if 'unsalvageable_reasons' in r:
                    for reason, count in r['unsalvageable_reasons'].items():
                        unsalvageable_reasons[reason] = unsalvageable_reasons.get(reason, 0) + count
                elif 'unsalvageable_reason' in r and r.get('unsalvageable', False):
                    reason = r['unsalvageable_reason']
                    unsalvageable_reasons[reason] = unsalvageable_reasons.get(reason, 0) + 1
            stats['unsalvageable_reasons'] = unsalvageable_reasons
            
            # Section extraction statistics
            thinking_rates = [r.get('thinking_extraction_rate', 0) for r in step_entries if 'thinking_extraction_rate' in r]
            response_rates = [r.get('response_extraction_rate', 0) for r in step_entries if 'response_extraction_rate' in r]
            
            if thinking_rates:
                stats['thinking_extraction_rate'] = sum(thinking_rates) / len(thinking_rates)
            if response_rates:
                stats['response_extraction_rate'] = sum(response_rates) / len(response_rates)
        
        # Joined benchmark statistics
        if any('main_model_correct_count' in r for r in entries):
            main_correct = sum(r.get('main_model_correct_count', 0) for r in entries)
            aux_correct = sum(r.get('aux_model_correct_count', 0) for r in entries)
            total_attempts = sum(r.get('total_attempts_per_model', 0) for r in entries)
            
            if total_attempts > 0:
                stats['main_model_success_rate'] = (main_correct / total_attempts) * 100
                stats['aux_model_success_rate'] = (aux_correct / total_attempts) * 100
                stats['main_vs_aux_diff'] = stats['main_model_success_rate'] - stats['aux_model_success_rate']
            
            # Use direct statistics from entries
            stats['both_correct_count'] = sum(r.get('both_correct_count', 0) for r in entries)
            stats['both_wrong_count'] = sum(r.get('both_wrong_count', 0) for r in entries)
            stats['disagreement_count'] = sum(r.get('disagreement_count', 0) for r in entries)
            stats['main_better_when_disagree'] = sum(r.get('main_better_when_disagree', 0) for r in entries)
            stats['aux_better_when_disagree'] = sum(r.get('aux_better_when_disagree', 0) for r in entries)
            
            # Calculate rates - use total_attempts_per_model to get the correct denominator
            total_attempts = sum(r.get('total_attempts_per_model', 0) for r in entries)
            stats['total_attempts'] = total_attempts  # Store for display
            if total_attempts > 0:
                stats['both_correct_rate'] = (stats['both_correct_count'] / total_attempts) * 100
                stats['both_wrong_rate'] = (stats['both_wrong_count'] / total_attempts) * 100
                stats['agreement_rate'] = ((stats['both_correct_count'] + stats['both_wrong_count']) / total_attempts) * 100
            else:
                stats['both_correct_rate'] = 0
                stats['both_wrong_rate'] = 0
                stats['agreement_rate'] = 0
            stats['disagreement_rate'] = (stats['disagreement_count'] / total) * 100 if total > 0 else 0
            
            if stats['disagreement_count'] > 0:
                stats['main_win_rate_when_disagree'] = (stats['main_better_when_disagree'] / stats['disagreement_count']) * 100
                stats['aux_win_rate_when_disagree'] = (stats['aux_better_when_disagree'] / stats['disagreement_count']) * 100
            
            # Track most common answer statistics
            stats['main_most_common_correct_count'] = sum(1 for r in entries if r.get('main_most_common_correct', False))
            stats['aux_most_common_correct_count'] = sum(1 for r in entries if r.get('aux_most_common_correct', False))
            stats['combined_most_common_correct_count'] = sum(1 for r in entries if r.get('combined_most_common_correct', False))
            
            stats['main_most_common_correct_rate'] = (stats['main_most_common_correct_count'] / total) * 100 if total > 0 else 0
            stats['aux_most_common_correct_rate'] = (stats['aux_most_common_correct_count'] / total) * 100 if total > 0 else 0
            stats['combined_most_common_correct_rate'] = (stats['combined_most_common_correct_count'] / total) * 100 if total > 0 else 0
            
        return stats


    def print_progress(self) -> None:
        """Print progress statistics for the last batch"""
        if not self.results:
            return
            
        # Get all statistics entries since last checkpoint
        total_stats = len([r for r in self.results if r.get('data_type') == 'statistics'])
        last_checkpoint = max(0, total_stats - self.config.stats_update_freq)
        stats_entries = [r for r in self.results if r.get('data_type') == 'statistics'][last_checkpoint:total_stats]
        if not stats_entries:
            return
            
        # Calculate statistics
        batch_stats = self._calculate_statistics(stats_entries)
        if not batch_stats:
            return
            
        # Build statistics string
        total_stats = len([r for r in self.results if r.get('data_type') == 'statistics'])
        stats_str = f"N={total_stats}\n\nBatch Statistics (last {self.config.stats_update_freq} examples):\n"
        
        # Basic statistics
        stats_str += (
            f"- Processing success rate: {batch_stats['processing_success_rate']:.1f}%\n"
            f"- Successfully processed examples: {batch_stats['successfully_processed']}/{batch_stats['total']} "
            f"({(batch_stats['successfully_processed']/batch_stats['total']*100):.1f}%)\n"
            f"- Problems with at least one correct solution: {batch_stats['at_least_one']}/{batch_stats['total']} "
            f"({(batch_stats['at_least_one']/batch_stats['total']*100):.1f}%)\n"
            f"- Average correct solutions per problem: {batch_stats['avg_correct']:.2f}\n"
            f"- Problems with above average initial correct solutions: {batch_stats['initial_above_avg']}/{batch_stats['total']} "
            f"({(batch_stats['initial_above_avg']/batch_stats['total']*100):.1f}%)\n"
            f"- Problems with above average final correct solutions: {batch_stats['final_above_avg']}/{batch_stats['total']} "
            f"({(batch_stats['final_above_avg']/batch_stats['total']*100):.1f}%)\n"
            f"- Problems where initial most common answer is correct: {batch_stats['initial_most_common_correct']}/{batch_stats['total']} "
            f"({(batch_stats['initial_most_common_correct']/batch_stats['total']*100):.1f}%)\n"
            f"- Problems where final most common answer is correct: {batch_stats['final_most_common_correct']}/{batch_stats['total']} "
            f"({(batch_stats['final_most_common_correct']/batch_stats['total']*100):.1f}%)\n"
        )
            
        # Add test verification statistics if present
        if 'test_passed_count' in batch_stats:
            stats_str += (
                f"\nTest Verification Statistics:\n"
                f"- Solutions passing tests: {batch_stats['test_passed_count']}/{batch_stats['total']} "
                f"({batch_stats['test_passed_rate']:.1f}%)\n"
                f"- Solutions both correct and passing tests: {batch_stats['verified_correct_count']}/{batch_stats['total']} "
                f"({batch_stats['verified_correct_rate']:.1f}%)\n"
            )
                
            if 'testing_improvement' in batch_stats:
                improvement = batch_stats['testing_improvement']
                sign = "+" if improvement >= 0 else ""
                stats_str += (
                    f"- Testing improvement: {sign}{improvement} examples ({batch_stats['testing_improvement_rate']:.1f}%)\n"
                    f"- Initial correct count: {batch_stats['initial_correct_count']}/{batch_stats['total']} "
                    f"({(batch_stats['initial_correct_count']/batch_stats['total']*100):.1f}%)\n"
                    f"- Final verified correct count: {batch_stats['final_correct_count']}/{batch_stats['total']} "
                    f"({(batch_stats['final_correct_count']/batch_stats['total']*100):.1f}%)\n"
                )
        
        # Tutor solution benchmark statistics if present
        if 'initial_solution_correct_count' in batch_stats:
            stats_str += (
                f"\nTutor Solution Benchmark Statistics:\n"
                f"- Initial Solutions Statistics:\n"
            )
            
            # Add best-of statistics if available
            if 'total_initial_solutions' in batch_stats:
                stats_str += (
                f"  - Total initial solutions: {batch_stats['total_initial_solutions']}\n"
                f"  - Total correct initial solutions: {batch_stats['total_initial_correct']}/{batch_stats['total_initial_solutions']} "
                f"({batch_stats['overall_initial_success_rate']:.1f}%)\n"
                f"  - Examples with at least one correct solution: {batch_stats['examples_with_at_least_one_correct']}/{batch_stats['total']} "
                f"({batch_stats['examples_with_at_least_one_correct_rate']:.1f}%)\n"
                f"  - Initial majority vote correct: {batch_stats['initial_majority_correct_count']}/{batch_stats['total']} "
                f"({batch_stats['initial_majority_correct_rate']:.1f}%)\n"
                f"\n- Final Solutions Statistics:\n"
                f"  - Total final solutions: {batch_stats['total_final_solutions']}\n"
                f"  - Total correct final solutions: {batch_stats['total_final_correct']}/{batch_stats['total_final_solutions']} "
                f"({batch_stats['overall_final_success_rate']:.1f}%)\n"
                f"  - Final majority vote correct: {batch_stats['final_majority_correct_count']}/{batch_stats['total']} "
                f"({batch_stats['final_majority_correct_rate']:.1f}%)\n"
                f"\n- Improvement Statistics:\n"
                f"  - Majority vote improved: {batch_stats['majority_vote_improved_count']}/{batch_stats['total']} "
                f"({batch_stats['majority_vote_improved_rate']:.1f}%)\n"
                f"  - Majority vote worsened: {batch_stats['majority_vote_worsened_count']}/{batch_stats['total']} "
                f"({batch_stats['majority_vote_worsened_rate']:.1f}%)\n"
                f"  - Overall success rate improved: {batch_stats['success_rate_improved_count']}/{batch_stats['total']} "
                f"({batch_stats['success_rate_improved_rate']:.1f}%)\n"
                f"  - Solution sources: {batch_stats['solution_sources']}\n"
            )
            
            # Add quality improvement statistics if available
            if 'quality_improved_count' in batch_stats:
                stats_str += (
                f"\nSolution Quality Metrics:\n"
                f"- Initial average quality: {batch_stats['initial_avg_quality']:.4f}\n"
                f"- Final average quality: {batch_stats['final_avg_quality']:.4f}\n"
                f"- Quality improvement: {(batch_stats['initial_avg_quality'] - batch_stats['final_avg_quality']):.4f}\n"
                f"- Solutions with improved quality: {batch_stats['quality_improved_count']}/{batch_stats.get('valid_quality_entries', batch_stats['total'])} "
                f"({batch_stats['quality_improved_rate']:.1f}%)\n"
                f"- Solutions with worsened quality: {batch_stats['quality_worsened_count']}/{batch_stats.get('valid_quality_entries', batch_stats['total'])} "
                f"({batch_stats['quality_worsened_rate']:.1f}%)\n"
            )
            
        # Joined benchmark statistics if present
        if 'main_model_success_rate' in batch_stats:
            stats_str += (
                f"\nModel Comparison:\n"
                f"- Main model success rate: {batch_stats['main_model_success_rate']:.1f}%\n"
                f"- Auxiliary model success rate: {batch_stats['aux_model_success_rate']:.1f}%\n"
                f"- Performance difference (main - aux): {batch_stats['main_vs_aux_diff']:.1f}%\n"
                f"\nModel Agreement:\n"
                f"- Both models correct: {batch_stats['both_correct_count']}/{batch_stats['total_attempts']} "
                f"({batch_stats['both_correct_rate']:.1f}%)\n"
                f"- Both models wrong: {batch_stats['both_wrong_count']}/{batch_stats['total_attempts']} "
                f"({batch_stats['both_wrong_rate']:.1f}%)\n"
                f"- Overall agreement rate: {batch_stats['agreement_rate']:.1f}%\n"
            )
            
            if 'disagreement_count' in batch_stats and batch_stats['disagreement_count'] > 0:
                stats_str += (
                    f"\nDisagreement Analysis:\n"
                    f"- Disagreement count: {batch_stats['disagreement_count']}/{batch_stats['total']} "
                    f"({batch_stats['disagreement_rate']:.1f}%)\n"
                    f"- Main model wins when disagreeing: {batch_stats['main_better_when_disagree']}/{batch_stats['disagreement_count']} "
                    f"({batch_stats['main_win_rate_when_disagree']:.1f}%)\n"
                    f"- Auxiliary model wins when disagreeing: {batch_stats['aux_better_when_disagree']}/{batch_stats['disagreement_count']} "
                    f"({batch_stats['aux_win_rate_when_disagree']:.1f}%)\n"
                )
                
            # Add most common answer statistics
            if 'main_most_common_correct_count' in batch_stats:
                stats_str += (
                    f"\nMost Common Answer Analysis:\n"
                    f"- Main model most common answer correct: {batch_stats['main_most_common_correct_count']}/{batch_stats['total']} "
                    f"({batch_stats['main_most_common_correct_rate']:.1f}%)\n"
                    f"- Auxiliary model most common answer correct: {batch_stats['aux_most_common_correct_count']}/{batch_stats['total']} "
                    f"({batch_stats['aux_most_common_correct_rate']:.1f}%)\n"
                    f"- Combined models most common answer correct: {batch_stats['combined_most_common_correct_count']}/{batch_stats['total']} "
                    f"({batch_stats['combined_most_common_correct_rate']:.1f}%)\n"
                )
        
        # Judge statistics if present
        if 'judge_decisions' in batch_stats:
            stats_str += (
                f"\nJudge Statistics:\n"
                f"- Judge decisions made: {batch_stats['judge_decisions']}\n"
                f"- Judge accuracy: {batch_stats['avg_judge_accuracy']:.1f}%\n"
            )
            
        # Step benchmark statistics if present
        if 'wrong_steps_found' in batch_stats:
            stats_str += (
                f"\nStep Benchmark Statistics:\n"
                f"- Wrong steps identified: {batch_stats['wrong_steps_found']}\n"
            )
            
            if 'avg_wrong_step_position' in batch_stats:
                stats_str += f"- Average wrong step position: {batch_stats['avg_wrong_step_position']:.2f}\n"
                
            if 'position_distribution' in batch_stats:
                stats_str += f"- Position distribution: {batch_stats['position_distribution']}\n"
                
            if 'avg_completion_score' in batch_stats:
                stats_str += f"- Average completion score: {batch_stats['avg_completion_score']:.2f}\n"
                
            if 'recovery_success_rate' in batch_stats:
                stats_str += f"- Recovery success rate: {batch_stats['recovery_success_rate']:.2f}\n"
                
            if 'unsalvageable_solutions' in batch_stats:
                stats_str += f"- Unsalvageable solutions: {batch_stats['unsalvageable_solutions']}\n"
                
            if 'unsalvageable_reasons' in batch_stats:
                stats_str += f"- Unsalvageable reasons: {batch_stats['unsalvageable_reasons']}\n"
                
            if 'thinking_extraction_rate' in batch_stats:
                stats_str += f"- Thinking extraction rate: {batch_stats['thinking_extraction_rate']:.2f}\n"
                
            if 'response_extraction_rate' in batch_stats:
                stats_str += f"- Response extraction rate: {batch_stats['response_extraction_rate']:.2f}\n"
            
        # Calculate accumulated statistics
        acc_stats = self._calculate_statistics([r for r in self.results if r.get('data_type') == 'statistics'])
        if acc_stats:
            stats_str += f"\nAccumulated Statistics (N={acc_stats['total']}):\n"
            stats_str += (
                f"- Processing success rate: {acc_stats['processing_success_rate']:.1f}%\n"
                f"- Successfully processed examples: {acc_stats['successfully_processed']}/{acc_stats['total']} "
                f"({acc_stats['processing_success_rate']:.1f}%)\n"
                f"- Problems with at least one correct solution: {acc_stats['at_least_one']}/{acc_stats['total']} "
                f"({(acc_stats['at_least_one']/acc_stats['total']*100):.1f}%)\n"
                f"- Average correct solutions per problem: {acc_stats['avg_correct']:.2f}\n"
                f"- Problems with above average initial correct solutions: {acc_stats['initial_above_avg']}/{acc_stats['total']} "
                f"({(acc_stats['initial_above_avg']/acc_stats['total']*100):.1f}%)\n"
                f"- Problems with above average final correct solutions: {acc_stats['final_above_avg']}/{acc_stats['total']} "
                f"({(acc_stats['final_above_avg']/acc_stats['total']*100):.1f}%)\n"
                f"- Problems where initial most common answer is correct: {acc_stats['initial_most_common_correct']}/{acc_stats['total']} "
                f"({(acc_stats['initial_most_common_correct']/acc_stats['total']*100):.1f}%)\n"
                f"- Problems where final most common answer is correct: {acc_stats['final_most_common_correct']}/{acc_stats['total']} "
                f"({(acc_stats['final_most_common_correct']/acc_stats['total']*100):.1f}%)\n"
            )
            
            # Add test verification statistics if present in accumulated stats
            if 'test_passed_count' in acc_stats:
                stats_str += (
                    f"\nTest Verification Statistics:\n"
                    f"- Solutions passing tests: {acc_stats['test_passed_count']}/{acc_stats['total']} "
                    f"({acc_stats['test_passed_rate']:.1f}%)\n"
                    f"- Solutions both correct and passing tests: {acc_stats['verified_correct_count']}/{acc_stats['total']} "
                    f"({acc_stats['verified_correct_rate']:.1f}%)\n"
                )
                
                if 'testing_improvement' in acc_stats:
                    improvement = acc_stats['testing_improvement']
                    sign = "+" if improvement >= 0 else ""
                    stats_str += (
                        f"- Testing improvement: {sign}{improvement} examples ({acc_stats['testing_improvement_rate']:.1f}%)\n"
                        f"- Initial correct count: {acc_stats['initial_correct_count']}/{acc_stats['total']} "
                        f"({(acc_stats['initial_correct_count']/acc_stats['total']*100):.1f}%)\n"
                        f"- Final verified correct count: {acc_stats['final_correct_count']}/{acc_stats['total']} "
                        f"({(acc_stats['final_correct_count']/acc_stats['total']*100):.1f}%)\n"
                    )
            
            # Tutor solution benchmark statistics if present in accumulated stats
            if 'initial_solution_correct_count' in acc_stats:
                stats_str += (
                    f"\nTutor Solution Benchmark Statistics:\n"
                    f"- Initial Solutions Statistics:\n"
                )
                
                # Add best-of statistics if available
                if 'total_initial_solutions' in acc_stats:
                    stats_str += (
                    f"  - Total initial solutions: {acc_stats['total_initial_solutions']}\n"
                    f"  - Total correct initial solutions: {acc_stats['total_initial_correct']}/{acc_stats['total_initial_solutions']} "
                    f"({acc_stats['overall_initial_success_rate']:.1f}%)\n"
                    f"  - Examples with at least one correct solution: {acc_stats['examples_with_at_least_one_correct']}/{acc_stats['total']} "
                    f"({acc_stats['examples_with_at_least_one_correct_rate']:.1f}%)\n"
                    f"  - Initial majority vote correct: {acc_stats['initial_majority_correct_count']}/{acc_stats['total']} "
                    f"({acc_stats['initial_majority_correct_rate']:.1f}%)\n"
                    f"\n- Final Solutions Statistics:\n"
                    f"  - Total final solutions: {acc_stats['total_final_solutions']}\n"
                    f"  - Total correct final solutions: {acc_stats['total_final_correct']}/{acc_stats['total_final_solutions']} "
                    f"({acc_stats['overall_final_success_rate']:.1f}%)\n"
                    f"  - Final majority vote correct: {acc_stats['final_majority_correct_count']}/{acc_stats['total']} "
                    f"({acc_stats['final_majority_correct_rate']:.1f}%)\n"
                    f"\n- Improvement Statistics:\n"
                    f"  - Majority vote improved: {acc_stats['majority_vote_improved_count']}/{acc_stats['total']} "
                    f"({acc_stats['majority_vote_improved_rate']:.1f}%)\n"
                    f"  - Majority vote worsened: {acc_stats['majority_vote_worsened_count']}/{acc_stats['total']} "
                    f"({acc_stats['majority_vote_worsened_rate']:.1f}%)\n"
                    f"  - Overall success rate improved: {acc_stats['success_rate_improved_count']}/{acc_stats['total']} "
                    f"({acc_stats['success_rate_improved_rate']:.1f}%)\n"
                    f"  - Solution sources: {acc_stats['solution_sources']}\n"
                )
                
                # Add quality improvement statistics if available
                if 'quality_improved_count' in acc_stats:
                    stats_str += (
                    f"\nSolution Quality Metrics:\n"
                    f"- Initial average quality: {acc_stats['initial_avg_quality']:.4f}\n"
                    f"- Final average quality: {acc_stats['final_avg_quality']:.4f}\n"
                    f"- Quality improvement: {(acc_stats['initial_avg_quality'] - acc_stats['final_avg_quality']):.4f}\n"
                    f"- Solutions with improved quality: {acc_stats['quality_improved_count']}/{acc_stats.get('valid_quality_entries', acc_stats['total'])} "
                    f"({acc_stats['quality_improved_rate']:.1f}%)\n"
                    f"- Solutions with worsened quality: {acc_stats['quality_worsened_count']}/{acc_stats.get('valid_quality_entries', acc_stats['total'])} "
                    f"({acc_stats['quality_worsened_rate']:.1f}%)\n"
                )
            
            # Joined benchmark statistics if present in accumulated stats
            if 'main_model_success_rate' in acc_stats:
                stats_str += (
                    f"\nModel Comparison:\n"
                    f"- Main model success rate: {acc_stats['main_model_success_rate']:.1f}%\n"
                    f"- Auxiliary model success rate: {acc_stats['aux_model_success_rate']:.1f}%\n"
                    f"- Performance difference (main - aux): {acc_stats['main_vs_aux_diff']:.1f}%\n"
                    f"\nModel Agreement:\n"
                    f"- Both models correct: {acc_stats['both_correct_count']}/{acc_stats['total_attempts']} "
                    f"({acc_stats['both_correct_rate']:.1f}%)\n"
                    f"- Both models wrong: {acc_stats['both_wrong_count']}/{acc_stats['total_attempts']} "
                    f"({acc_stats['both_wrong_rate']:.1f}%)\n"
                    f"- Overall agreement rate: {acc_stats['agreement_rate']:.1f}%\n"
                )
                
                if 'disagreement_count' in acc_stats and acc_stats['disagreement_count'] > 0:
                    stats_str += (
                        f"\nDisagreement Analysis:\n"
                        f"- Disagreement count: {acc_stats['disagreement_count']}/{acc_stats['total']} "
                        f"({acc_stats['disagreement_rate']:.1f}%)\n"
                        f"- Main model wins when disagreeing: {acc_stats['main_better_when_disagree']}/{acc_stats['disagreement_count']} "
                        f"({acc_stats['main_win_rate_when_disagree']:.1f}%)\n"
                        f"- Auxiliary model wins when disagreeing: {acc_stats['aux_better_when_disagree']}/{acc_stats['disagreement_count']} "
                        f"({acc_stats['aux_win_rate_when_disagree']:.1f}%)\n"
                    )
                    
                # Add most common answer statistics
                if 'main_most_common_correct_count' in acc_stats:
                    stats_str += (
                        f"\nMost Common Answer Analysis:\n"
                        f"- Main model most common answer correct: {acc_stats['main_most_common_correct_count']}/{acc_stats['total']} "
                        f"({acc_stats['main_most_common_correct_rate']:.1f}%)\n"
                        f"- Auxiliary model most common answer correct: {acc_stats['aux_most_common_correct_count']}/{acc_stats['total']} "
                        f"({acc_stats['aux_most_common_correct_rate']:.1f}%)\n"
                        f"- Combined models most common answer correct: {acc_stats['combined_most_common_correct_count']}/{acc_stats['total']} "
                        f"({acc_stats['combined_most_common_correct_rate']:.1f}%)\n"
                    )
            
            if 'tournament_winners' in acc_stats:
                stats_str += (
                    f"- Tournament winners correct: {acc_stats['tournament_winners']}/{acc_stats['total_tournaments']} "
                    f"({(acc_stats['tournament_winners']/acc_stats['total_tournaments']*100):.1f}%)\n"
                )
                    
            if 'judge_decisions' in acc_stats:
                stats_str += (
                    f"- Judge decisions made: {acc_stats['judge_decisions']}\n"
                    f"- Overall judge accuracy: {acc_stats['avg_judge_accuracy']:.1f}%\n"
                )
        
        print(stats_str)
        self._save_progress_stats(stats_str)
        
        # Create dataset if requested
        self.create_hf_dataset()

    def save_results(self) -> None:
        """Save results to JSON files by data type"""
        if not self.results:
            print("No results to save")
            return
        if not self.config.produce_statistics:
            print("Statistics production disabled")
            return

            
        try:
            # Create results directory if it doesn't exist
            os.makedirs("results", exist_ok=True)
            print(f"Total results to process: {len(self.results)}")
            
            # Group results by data type
            results_by_type = defaultdict(list)
            for r in self.results:
                data_type = r.get('data_type')
                if data_type:
                    results_by_type[data_type].append(r)
            
            print(f"Found data types: {list(results_by_type.keys())}")
            
            # Save timestamp for consistent filenames
            timestamp = self.start_time.strftime('%Y%m%d_%H%M%S')
            
            # Only save training data, not statistics
            if 'training' in results_by_type and results_by_type['training']:
                training_results = results_by_type['training']
                filename = f"training_{timestamp}.json"
                filepath = os.path.join("results", filename)
                print(f"Attempting to save {len(training_results)} training results to: {filepath}")
                with open(filepath, 'w') as f:
                    json.dump(training_results, f, indent=2)
                print(f"Successfully saved {len(training_results)} training results to: {filepath}")

        except Exception as e:
            print(f"Error saving results: {str(e)}")
            import traceback
            traceback.print_exc()

    def create_hf_dataset(self) -> None:
        """Create a HuggingFace dataset from the results"""
        if not self.results or not self.config.create_dataset:
            return
            
        # Create timestamp-based directory
        timestamp = self.start_time.strftime('%Y%m%d_%H%M%S')
        dataset_dir = os.path.join("local_datasets", timestamp)
        os.makedirs(dataset_dir, exist_ok=True)
        
        # Convert results to HuggingFace dataset
        dataset = Dataset.from_list(self.results)
        
        # Save locally in Arrow format
        dataset.save_to_disk(dataset_dir)
        print(f"\nDataset saved to: {dataset_dir}")

    def print_final_stats(self) -> None:
        if not self.results:
            msg = "\nNo examples were successfully processed."
            print(msg)
            self._save_progress_stats(msg + "\n")
            return

        # Get only statistics entries
        stats_entries = [r for r in self.results if r.get('data_type') == 'statistics']
        if not stats_entries:
            msg = "\nNo statistics entries were found in results."
            print(msg)
            self._save_progress_stats(msg + "\n")
            return

        # Use the common calculation method
        final_stats = self._calculate_statistics(stats_entries)
        total = final_stats['total']
        end_time = datetime.now()
        total_duration = end_time - self.start_time

        stats_str = (
            f"\nFinal Statistics (N={total}):\n"
            f"- Processing success rate: {final_stats['processing_success_rate']:.1f}%\n"
            f"- Successfully processed examples: {final_stats['successfully_processed']}/{total} "
            f"({final_stats['processing_success_rate']:.1f}%)\n"
            f"- Problems with at least one correct solution: {final_stats['at_least_one']}/{total} "
            f"({(final_stats['at_least_one']/total*100) if total > 0 else 0:.1f}%)\n"
            f"- Average correct solutions per problem: {final_stats['avg_correct']:.2f}\n"
            f"- Problems with above average initial correct solutions: {final_stats['initial_above_avg']}/{total} "
            f"({(final_stats['initial_above_avg']/total*100) if total > 0 else 0:.1f}%)\n"
            f"- Problems with above average final correct solutions: {final_stats['final_above_avg']}/{total} "
            f"({(final_stats['final_above_avg']/total*100) if total > 0 else 0:.1f}%)\n"
            f"- Problems where initial most common answer is correct: {final_stats['initial_most_common_correct']}/{total} "
            f"({(final_stats['initial_most_common_correct']/total*100) if total > 0 else 0:.1f}%)\n"
            f"- Problems where final most common answer is correct: {final_stats['final_most_common_correct']}/{total} "
            f"({(final_stats['final_most_common_correct']/total*100) if total > 0 else 0:.1f}%)\n"
        )
        
        # Add test verification statistics if present in final stats
        if 'test_passed_count' in final_stats:
            stats_str += (
                f"\nTest Verification Statistics:\n"
                f"- Solutions passing tests: {final_stats['test_passed_count']}/{total} "
                f"({final_stats['test_passed_rate']:.1f}%)\n"
                f"- Solutions both correct and passing tests: {final_stats['verified_correct_count']}/{total} "
                f"({final_stats['verified_correct_rate']:.1f}%)\n"
            )
            
            if 'testing_improvement' in final_stats:
                improvement = final_stats['testing_improvement']
                sign = "+" if improvement >= 0 else ""
                stats_str += (
                    f"- Testing improvement: {sign}{improvement} examples ({final_stats['testing_improvement_rate']:.1f}%)\n"
                    f"- Initial correct count: {final_stats['initial_correct_count']}/{total} "
                    f"({(final_stats['initial_correct_count']/total*100) if total > 0 else 0:.1f}%)\n"
                    f"- Final verified correct count: {final_stats['final_correct_count']}/{total} "
                    f"({(final_stats['final_correct_count']/total*100) if total > 0 else 0:.1f}%)\n"
                )

        # Tutor solution benchmark statistics if present
        if 'initial_solution_correct_count' in final_stats:
            stats_str += (
                f"\nTutor Solution Benchmark Statistics:\n"
                f"- Initial Solutions Statistics:\n"
            )
            
            # Add best-of statistics if available
            if 'total_initial_solutions' in final_stats:
                stats_str += (
                f"  - Total initial solutions: {final_stats['total_initial_solutions']}\n"
                f"  - Total correct initial solutions: {final_stats['total_initial_correct']}/{final_stats['total_initial_solutions']} "
                f"({final_stats['overall_initial_success_rate']:.1f}%)\n"
                f"  - Examples with at least one correct solution: {final_stats['examples_with_at_least_one_correct']}/{total} "
                f"({final_stats['examples_with_at_least_one_correct_rate']:.1f}%)\n"
                f"  - Initial majority vote correct: {final_stats['initial_majority_correct_count']}/{total} "
                f"({final_stats['initial_majority_correct_rate']:.1f}%)\n"
                f"\n- Final Solutions Statistics:\n"
                f"  - Total final solutions: {final_stats['total_final_solutions']}\n"
                f"  - Total correct final solutions: {final_stats['total_final_correct']}/{final_stats['total_final_solutions']} "
                f"({final_stats['overall_final_success_rate']:.1f}%)\n"
                f"  - Final majority vote correct: {final_stats['final_majority_correct_count']}/{total} "
                f"({final_stats['final_majority_correct_rate']:.1f}%)\n"
                f"\n- Improvement Statistics:\n"
                f"  - Majority vote improved: {final_stats['majority_vote_improved_count']}/{total} "
                f"({final_stats['majority_vote_improved_rate']:.1f}%)\n"
                f"  - Majority vote worsened: {final_stats['majority_vote_worsened_count']}/{total} "
                f"({final_stats['majority_vote_worsened_rate']:.1f}%)\n"
                f"  - Overall success rate improved: {final_stats['success_rate_improved_count']}/{total} "
                f"({final_stats['success_rate_improved_rate']:.1f}%)\n"
                f"  - Solution sources: {final_stats['solution_sources']}\n"
            )
            
            # Add quality improvement statistics if available
            if 'quality_improved_count' in final_stats:
                stats_str += (
                f"\nSolution Quality Metrics:\n"
                f"- Initial average quality: {final_stats['initial_avg_quality']:.4f}\n"
                f"- Final average quality: {final_stats['final_avg_quality']:.4f}\n"
                f"- Quality improvement: {(final_stats['initial_avg_quality'] - final_stats['final_avg_quality']):.4f}\n"
                f"- Solutions with improved quality: {final_stats['quality_improved_count']}/{final_stats.get('valid_quality_entries', total)} "
                f"({final_stats['quality_improved_rate']:.1f}%)\n"
                f"- Solutions with worsened quality: {final_stats['quality_worsened_count']}/{final_stats.get('valid_quality_entries', total)} "
                f"({final_stats['quality_worsened_rate']:.1f}%)\n"
            )
            
        # Joined benchmark statistics if present
        if 'main_model_success_rate' in final_stats:
            stats_str += (
                f"\nModel Comparison:\n"
                f"- Main model success rate: {final_stats['main_model_success_rate']:.1f}%\n"
                f"- Auxiliary model success rate: {final_stats['aux_model_success_rate']:.1f}%\n"
                f"- Performance difference (main - aux): {final_stats['main_vs_aux_diff']:.1f}%\n"
                f"\nModel Agreement:\n"
                f"- Both models correct: {final_stats['both_correct_count']}/{final_stats['total_attempts']} "
                f"({final_stats['both_correct_rate']:.1f}%)\n"
                f"- Both models wrong: {final_stats['both_wrong_count']}/{final_stats['total_attempts']} "
                f"({final_stats['both_wrong_rate']:.1f}%)\n"
                f"- Overall agreement rate: {final_stats['agreement_rate']:.1f}%\n"
            )
            
            if 'disagreement_count' in final_stats and final_stats['disagreement_count'] > 0:
                stats_str += (
                    f"\nDisagreement Analysis:\n"
                    f"- Disagreement count: {final_stats['disagreement_count']}/{total} "
                    f"({final_stats['disagreement_rate']:.1f}%)\n"
                    f"- Main model wins when disagreeing: {final_stats['main_better_when_disagree']}/{final_stats['disagreement_count']} "
                    f"({final_stats['main_win_rate_when_disagree']:.1f}%)\n"
                    f"- Auxiliary model wins when disagreeing: {final_stats['aux_better_when_disagree']}/{final_stats['disagreement_count']} "
                    f"({final_stats['aux_win_rate_when_disagree']:.1f}%)\n"
                )
                
            # Add most common answer statistics to final stats
            if 'main_most_common_correct_count' in final_stats:
                stats_str += (
                    f"\nMost Common Answer Analysis:\n"
                    f"- Main model most common answer correct: {final_stats['main_most_common_correct_count']}/{total} "
                    f"({final_stats['main_most_common_correct_rate']:.1f}%)\n"
                    f"- Auxiliary model most common answer correct: {final_stats['aux_most_common_correct_count']}/{total} "
                    f"({final_stats['aux_most_common_correct_rate']:.1f}%)\n"
                    f"- Combined models most common answer correct: {final_stats['combined_most_common_correct_count']}/{total} "
                    f"({final_stats['combined_most_common_correct_rate']:.1f}%)\n"
                )

        # Judge statistics if present
        if 'judge_decisions' in final_stats:
            stats_str += (
                f"\nJudge Statistics:\n"
                f"- Judge decisions made: {final_stats['judge_decisions']}\n"
                f"- Overall judge accuracy: {final_stats['avg_judge_accuracy']:.1f}%\n"
            )
            
        # Step benchmark statistics if present
        if 'wrong_steps_found' in final_stats:
            stats_str += (
                f"\nStep Benchmark Statistics:\n"
                f"- Total wrong steps identified: {final_stats['wrong_steps_found']}\n"
            )
            
            if 'avg_wrong_step_position' in final_stats:
                stats_str += f"- Average wrong step position: {final_stats['avg_wrong_step_position']:.2f}\n"
                
            if 'position_distribution' in final_stats:
                stats_str += f"- Position distribution: {final_stats['position_distribution']}\n"
                
            if 'avg_completion_score' in final_stats:
                stats_str += f"- Average completion score: {final_stats['avg_completion_score']:.2f}\n"
                
            if 'recovery_success_rate' in final_stats:
                stats_str += f"- Average recovery success rate: {final_stats['recovery_success_rate']:.2f}\n"
                
            if 'unsalvageable_solutions' in final_stats:
                stats_str += f"- Total unsalvageable solutions: {final_stats['unsalvageable_solutions']}\n"
                
            if 'unsalvageable_reasons' in final_stats:
                stats_str += f"- Unsalvageable reasons: {final_stats['unsalvageable_reasons']}\n"
                
            if 'thinking_extraction_rate' in final_stats:
                stats_str += f"- Average thinking extraction rate: {final_stats['thinking_extraction_rate']:.2f}\n"
                
            if 'response_extraction_rate' in final_stats:
                stats_str += f"- Average response extraction rate: {final_stats['response_extraction_rate']:.2f}\n"

        stats_str += f"\n- Total runtime: {total_duration.total_seconds():.1f}s"

        print(stats_str)
        self._save_progress_stats(stats_str)
    async def run_benchmark(
        self,
        process_example_func: Callable
    ) -> None:
        # Set up signal handlers
        import signal
        
        def signal_handler(signum, frame):
            print("\nReceived interrupt signal. Saving current results...")
            # Force save by temporarily setting produce_statistics to True
            original_setting = self.config.produce_statistics
            self.config.produce_statistics = True
            self.save_results()
            self.config.produce_statistics = original_setting
            self.print_final_stats()
            print("\nResults saved. Exiting...")
            exit(0)
            
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        """Generic benchmark runner that handles dataset loading and example processing"""
        if self.config.max_concurrent < 1:
            print("Error: Maximum concurrent problems must be at least 1")
            return

        # Load exclude list if provided
        excluded_problems = set()
        if self.config.exclude and os.path.exists(self.config.exclude):
            try:
                with open(self.config.exclude, 'r') as f:
                    exclude_data = json.load(f)
                    excluded_problems = {item['problem'] for item in exclude_data if 'problem' in item}
                print(f"Loaded {len(excluded_problems)} problems to exclude")
            except Exception as e:
                print(f"Error loading exclude file: {e}")
                return

        try:
            # Create a unique cache directory using timestamp
            timestamp = int(time.time())
            cache_dir = os.path.join("cache", f"huggingface_{timestamp}")
            os.makedirs(cache_dir, exist_ok=True)

            def load_dataset_with_retry(max_retries=3, cleanup_on_fail=True):
                for attempt in range(max_retries):
                    try:
                        if os.path.exists(self.config.dataset):  # Local path
                            full_dataset = load_from_disk(self.config.dataset)
                            
                            # Handle slicing for local dataset
                            dataset = full_dataset
                            if self.config.split:
                                if '[' in self.config.split:
                                    # Extract slice indices
                                    base_split, slice_part = self.config.split.split('[')
                                    slice_part = slice_part.rstrip(']')
                                    if ':' in slice_part:
                                        start, end = map(lambda x: int(x) if x else None, slice_part.split(':'))
                                        # Apply slice
                                        dataset = dataset.select(range(start if start else 0, end if end else len(dataset)))
                            
                        else:  # HuggingFace dataset
                            # Handle split and slice
                            split_name = self.config.split or 'train'
                            if '[' in split_name:
                                # Extract slice indices
                                base_split, slice_part = split_name.split('[')
                                slice_part = slice_part.rstrip(']')
                                if ':' in slice_part:
                                    start, end = map(lambda x: int(x) if x else None, slice_part.split(':'))
                                    # Load full split then slice
                                    if self.config.dataset == 'Metaskepsis/Numina':
                                        dataset = load_dataset(
                                            "Metaskepsis/Numina",
                                            split=base_split,
                                            cache_dir=cache_dir,
                                            download_mode="force_redownload" if attempt > 0 else "reuse_cache_if_exists"
                                        )
                                    else:
                                        dataset = load_dataset(
                                            self.config.dataset,
                                            split=base_split,
                                            cache_dir=cache_dir,
                                            download_mode="force_redownload" if attempt > 0 else "reuse_cache_if_exists"
                                        )
                                    # Apply slice
                                    dataset = dataset.select(range(start if start else 0, end if end else len(dataset)))
                            else:
                                # No slice, load normally
                                if self.config.dataset == 'Metaskepsis/Numina':
                                    dataset = load_dataset(
                                        "Metaskepsis/Numina",
                                        split=split_name,
                                        cache_dir=cache_dir,
                                        download_mode="force_redownload" if attempt > 0 else "reuse_cache_if_exists"
                                    )
                                else:
                                    dataset = load_dataset(
                                        self.config.dataset,
                                        split=split_name,
                                        cache_dir=cache_dir,
                                        download_mode="force_redownload" if attempt > 0 else "reuse_cache_if_exists"
                                    )
                        return dataset
                    except Exception as e:
                        print(f"Dataset loading attempt {attempt + 1} failed: {str(e)}")
                        if cleanup_on_fail and attempt < max_retries - 1:
                            print("Cleaning up cache and retrying...")
                            try:
                                shutil.rmtree(cache_dir)
                                os.makedirs(cache_dir, exist_ok=True)
                            except Exception as cleanup_error:
                                print(f"Cache cleanup failed: {cleanup_error}")
                        time.sleep(2)  # Wait before retry
                        
                raise Exception("Failed to load dataset after all retries")

            try:
                dataset = load_dataset_with_retry()
                
                # Handle DatasetDict
                if isinstance(dataset, dict) and 'train' in dataset:
                    dataset = dataset['train']
                elif hasattr(dataset, 'train'):  # DatasetDict object
                    dataset = dataset['train']
                
                # Now that we have a Dataset object, process features
                if hasattr(dataset, 'features'):
                    # Add auto-incrementing ID if it doesn't exist
                    if 'id' not in dataset.features:
                        dataset = dataset.map(lambda x, idx: {'id': idx}, with_indices=True)
                    
                    # Convert 'question' to 'problem' if needed
                    if 'question' in dataset.features and 'problem' not in dataset.features:
                        dataset = dataset.map(lambda x: {'problem': x['question'], **{k:v for k,v in x.items() if k != 'question'}})
                    
                    # Create solution from answer if needed
                    if 'answer' in dataset.features and 'solution' not in dataset.features:
                        dataset = dataset.map(lambda x: {'solution': f"\\boxed{{{x['answer']}}}", **x})
                else:
                    print("Warning: Dataset does not have features attribute")
                    
            except Exception as e:
                print(f"Fatal error loading dataset: {e}")
                return
            
            # First sort by ID to ensure consistent ordering
            dataset = dataset.sort('id')
                
            # Filter out excluded problems
            if excluded_problems:
                dataset = dataset.filter(lambda x: x['problem'] not in excluded_problems)
                print(f"Filtered dataset to exclude {len(excluded_problems)} problems")
                
            # Shuffle dataset with seed if specified
            if self.config.seed is not None:
                dataset = dataset.shuffle(seed=self.config.seed)
                
            if self.config.split_slice:
                dataset = dataset.select(range(*self.config.split_slice.indices(len(dataset))))
        except Exception as e:
            print(f"Error loading dataset: {e}")
            return

        if self.config.split_slice:
            dataset_length = min(self.config.split_slice.stop, len(dataset))
        else:
            dataset_length = len(dataset)

        self.total_examples = dataset_length

        example_data = []
        for example in dataset:
            # Preserve all fields from the original dataset
            processed = {key: example[key] for key in example.keys()}
            example_data.append(processed)

        if not example_data:
            print("No valid examples to process after initial filtering.")
            return

        print(f"\nStarting processing of {self.total_examples} examples...")
        try:
            semaphore = asyncio.Semaphore(self.config.max_concurrent)

            async def process_with_semaphore(example: Dict, running_id: int) -> Optional[Dict]:
                async with semaphore:
                    result = await process_example_func(
                        example=example,
                        running_id=running_id,
                        example_id=example['id'],
                        config=self.config
                    )
                    return result

            tasks = [process_with_semaphore(ex, i) for i, ex in enumerate(example_data)]
            
            print(f"\nWill process {len(example_data)} examples")
            
            progress_bar = tqdm(total=len(example_data), desc="Processing examples")
            all_logs = []
            
            for coro in asyncio.as_completed(tasks):
                try:
                    result = await coro
                    if result:
                        # Handle both old format (direct list) and new format (dict with 'results' key)
                        if isinstance(result, dict):
                            if 'logs' in result and result['logs']:
                                all_logs.append(result['logs'])
                            if 'results' in result:
                                self.add_result(result['results'])
                            if 'total_solution_attempts' in result:
                                all_logs.append(f"\nTotal solution attempts for example {len(self.results)}: {result['total_solution_attempts']}")
                        else:
                            # Old format - direct list of results
                            self.add_result(result)
                    progress_bar.update(1)
                except Exception as e:
                    all_logs.append(f"Error processing example: {str(e)}")
                    print(f"Exception in processing example: {str(e)}")
            progress_bar.close()
        
        finally:
            # Print all collected logs
            print("\n" + "="*80)
            print("COMPLETE LOG OUTPUT")
            print("="*80)
            for log in all_logs:
                if log:  # Only print non-empty logs
                    print("\n" + log)
            print("\n" + "="*80)
            
            # Force final save of results
            original_setting = self.config.produce_statistics
            self.config.produce_statistics = True
            self.save_results()
            self.config.produce_statistics = original_setting
            
            self.print_final_stats()
            
            # Cleanup cache directory at the end
            try:
                shutil.rmtree(cache_dir)
            except Exception as e:
                print(f"Warning: Failed to cleanup cache directory: {e}")
