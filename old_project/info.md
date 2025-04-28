# How to Ask an LLM for a Progress Tracker Implementation

This guide explains how to request a comprehensive progress tracker implementation from an LLM for your projects.

## What is a Progress Tracker?

A progress tracker is a component that monitors and reports on the execution of long-running tasks, providing:
- Real-time progress updates
- Statistics on success rates and performance
- ETA estimation
- Result aggregation and reporting
- Checkpoint saving for resumable operations

## How to Request a Progress Tracker

When asking an LLM to implement a progress tracker, be specific about your requirements. Here's a template request:

```
I need a comprehensive progress tracker for my [type of application] that handles:

1. Tracking progress of [specific task type] with real-time updates
2. Collecting and aggregating statistics on [specific metrics]
3. Handling checkpoints for resumable operations
4. Generating detailed reports with [specific format/requirements]
5. Supporting parallel processing with [concurrency requirements]

The tracker should integrate with [specific frameworks/libraries] and support [specific output formats].
```

## Key Components to Request

### Core Functionality
- **Progress Monitoring**: Ask for methods to update and display progress (percentage complete, items processed)
- **Statistics Collection**: Request functionality to gather metrics during processing
- **Result Aggregation**: Ask for methods to combine and summarize results
- **Checkpoint Management**: Request functionality to save state for resumable operations
- **Reporting**: Ask for detailed report generation with configurable formats

### Integration Points
- **Event Handling**: Request hooks for progress events and completion notifications
- **Concurrency Support**: Ask for thread-safe operations if using parallel processing
- **Framework Integration**: Request compatibility with specific frameworks (asyncio, threading, etc.)
- **Visualization**: Ask for integration with visualization libraries if needed

### Advanced Features
- **ETA Calculation**: Request time estimation for completion
- **Resource Monitoring**: Ask for tracking of CPU/memory usage during processing
- **Adaptive Rate Limiting**: Request throttling based on system load
- **Failure Recovery**: Ask for strategies to handle and recover from errors
- **Distributed Tracking**: Request support for tracking across multiple processes/machines

## Example Implementation Reference

For reference, see the `ProgressTracker` class in `utils/progress_tracker.py` which demonstrates:
- Comprehensive statistics tracking with component breakdowns
- Support for different data types and processing models
- Real-time progress updates with ETA estimation
- Result saving in multiple formats
- Integration with asynchronous processing

## Customization Tips

When requesting a progress tracker, consider these customization points:
- **Verbosity Levels**: Ask for configurable detail in progress reporting
- **Output Formats**: Specify desired formats (console, JSON, CSV, etc.)
- **Visualization Options**: Request specific charts or displays for progress
- **Persistence Strategy**: Specify how and when to save progress data
- **Notification Mechanisms**: Request alerts for completion or errors

## Integration Example

Request an example of how to integrate the progress tracker with your specific workflow:

```python
# Example integration with your processing loop
tracker = ProgressTracker(total_items=1000, config=config)

for item in items:
    result = process_item(item)
    tracker.add_result([result])
    # Check if should display progress update
    if tracker.should_update():
        tracker.print_progress()

# Final statistics and reporting
tracker.print_final_stats()
tracker.save_results()
```

By following this guide, you'll be able to request and receive a well-designed progress tracker that meets your specific project requirements.
