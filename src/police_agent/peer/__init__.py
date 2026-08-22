"""The other process: handshake, wire protocol, turn loop and summaries.

This layer owns everything that is true only because there are two independent
processes -- agreeing terms before a game, sealing and revealing commitments,
taking turns over a link that can stall, and surviving an opponent that stops
answering. `domain/` decides what a move means; `peer/` is how a move gets
there and how its arrival is proved.

Nothing in here may import the opponent's implementation, and nothing may hold
the opponent's private state: what this package knows about the thief is what
the thief chose to send, plus what the end-of-game audit can verify.
"""
