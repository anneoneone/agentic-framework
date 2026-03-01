# Using Your New Rust Specialist Agents

**Generated**: January 14, 2026  
**Location**: `.github/agents/`  
**Workspace**: rust-ebee.code-workspace

## ✅ Agents Created

Five specialist agents are now available for Rust development in the ebee monorepo:

1. **@rust-expert** - General Rust patterns, ownership, traits, error handling
2. **@async-tokio** - Tokio runtime, async/await, channels, cancellation
3. **@ocpp-protocol** - OCPP 2.0.1 protocol, transactions, state machines
4. **@grpc-integration** - Tonic/gRPC services, protobuf, streaming
5. **@rust-test-expert** - Testing with tokio::test, mockall, integration tests

## Quick Start

### Step 1: Open the Rust workspace
```bash
code ~/0_git/0_ebee_meta_projects/monorepo/rust-ebee.code-workspace
```

### Step 2: Start using agents

**Example 1: Understanding code**
```
@rust-expert explain the ownership pattern in this Transaction struct
```

**Example 2: Async help**
```
@async-tokio how do I handle cancellation in this select! block?
```

**Example 3: OCPP questions**
```
@ocpp-protocol what sequence of messages should I send when starting a transaction?
```

**Example 4: gRPC implementation**
```
@grpc-integration how do I implement server streaming for meter values?
```

**Example 5: Writing tests**
```
@rust-test-expert write tests for this transaction lifecycle
```

## Common Workflows

### Adding a new OCPP message handler

1. **Design the handler** with @ocpp-protocol:
   ```
   @ocpp-protocol I need to implement RemoteStartTransaction handler. What fields are required?
   ```

2. **Implement async logic** with @async-tokio:
   ```
   @async-tokio how do I spawn a background task for this charging session?
   ```

3. **Review Rust patterns** with @rust-expert:
   ```
   @rust-expert is this error handling pattern idiomatic?
   ```

4. **Write tests** with @rust-test-expert:
   ```
   @rust-test-expert write unit tests for RemoteStartTransaction handler
   ```

### Building a new gRPC service

1. **Define protobuf** with @grpc-integration:
   ```
   @grpc-integration create a protobuf definition for diagnostics service
   ```

2. **Implement service** with @rust-expert and @async-tokio:
   ```
   @rust-expert how should I structure the service implementation?
   @async-tokio how do I handle streaming responses?
   ```

3. **Test the service** with @rust-test-expert:
   ```
   @rust-test-expert how do I test gRPC streaming with mocked data?
   ```

### Debugging async issues

1. **Identify problem** with @async-tokio:
   ```
   @async-tokio why is this actor not receiving messages?
   ```

2. **Check patterns** with @rust-expert:
   ```
   @rust-expert are there ownership issues with this channel setup?
   ```

3. **Add tests** with @rust-test-expert:
   ```
   @rust-test-expert write a test that reproduces this deadlock
   ```

## Agent Coordination

Agents work together and know when to delegate:

**Scenario: Transaction persistence issue**
```
You: @ocpp-protocol why isn't my transaction being persisted?

@ocpp-protocol: The transaction needs to be saved before sending TransactionEvent.
Check the persistence service integration...
[For async persistence patterns, consult @async-tokio]
[For error handling, consult @rust-expert]
```

**Scenario: Testing async code**
```
You: @rust-test-expert how do I test this OCPP state machine?

@rust-test-expert: Use #[tokio::test(start_paused = true)] for time mocking...
[For OCPP message sequences, consult @ocpp-protocol]
[For mocking async actors, consult @async-tokio]
```

## Tips for Best Results

### Be specific
❌ "How do I fix this?"  
✅ "Why is this transaction.start() returning an error about persistence?"

### Provide context
❌ "Add error handling"  
✅ "Add error handling to this WebSocket connection with proper reconnection logic"

### Reference files
❌ "Update the code"  
✅ "Update src/ocpp/backend_handler/backend_connector.rs to handle reconnection"

### Ask follow-up questions
After getting an answer, dig deeper:
```
@async-tokio thanks! Now how do I test this cancellation logic?
```

## Commands You'll Use Often

### Building
```bash
cargo build -p ocpp20              # Build OCPP package
cargo check                        # Fast type checking
cargo clippy                       # Linting
cargo fmt                          # Format code
```

### Testing
```bash
cargo test -p ocpp20                         # Test OCPP
cargo test -- --nocapture                    # See output
cargo test test_transaction                  # Specific test
RUST_LOG=debug cargo test -- --nocapture     # With logs
```

### Documentation
```bash
cargo doc -p ocpp20 --open         # View docs
```

## Cross-Stack Work

When you need to work across Rust, Python, or C++:

1. **Use @coordinator** (available in all workspaces):
   ```
   @coordinator I need to add diagnostics in Rust and test it in Python
   ```

2. **Switch workspaces** as directed:
   - Rust work: `rust-ebee.code-workspace`
   - Python tests: `python-test.code-workspace`
   - C++ firmware: `cpp-firmware.code-workspace`

3. **Reference shared-context.md** for cross-language interfaces:
   - Protobuf definitions
   - gRPC contracts
   - Error handling patterns

## Troubleshooting

### Agent not responding as expected?
- Make sure you're in the correct workspace (rust-ebee.code-workspace)
- Be more specific in your question
- Try a different agent if it's outside their scope

### Need more than one agent?
Ask them in sequence:
```
@ocpp-protocol what's the message flow for authorization?
[Review answer]
@async-tokio how do I implement this flow with proper error handling?
[Review answer]
@rust-test-expert now write tests for this authorization flow
```

### Contradictory advice?
- @rust-expert has final say on Rust idioms
- @async-tokio has final say on tokio patterns
- @ocpp-protocol has final say on OCPP spec compliance
- @rust-test-expert has final say on testing strategies

## Next Steps

1. ✅ Read this guide
2. ✅ Open rust-ebee.code-workspace
3. ✅ Try asking @rust-expert a simple question
4. ✅ Use agents for your current task
5. ✅ Refer back to agent files in `.github/agents/` for detailed examples

## Feedback Loop

As you use these agents:
- Note what works well
- Identify gaps in their knowledge
- Update agent definitions as needed
- Share learnings with the team

## Resources

- Agent definitions: `.github/agents/*.agent.md`
- Analysis: `ANALYSIS_ebee_rust_agents.md`
- Shared context: `.github/agents/shared-context.md`
- OCPP docs: `appfs/ebee/ocpp20/TRANSACTION_PERSISTENCE_*.md`

---

**Happy coding with your new specialist agents! 🦀**
