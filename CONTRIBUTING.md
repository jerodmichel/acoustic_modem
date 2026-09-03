# Contributing to Acoustic Modem

First off, thank you for considering contributing to this project! It's people like you that make the open-source community a great place to inspire, and be inspired.

## How Can I Contribute?

### Reporting Bugs
If you find a bug, please open an issue and include:
* Your operating system and Python version.
* The exact command you ran.
* What you expected to happen, and what actually happened.
* A copy of any error logs.

### Suggesting Enhancements
Security research is an evolving field. If you have ideas for new error-correcting codes, better DSP tracking loops, or new features:
* Open an issue to discuss your idea first.
* Provide a clear description of the enhancement and why it is useful for acoustic/air-gap research.

### Pull Requests
1. Fork the repository.
2. Create a new branch (`git checkout -b feature/AmazingFeature`).
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`).
4. Push to the branch (`git push origin feature/AmazingFeature`).
5. Open a Pull Request.

## Code Style
* Keep the DSP and math engines isolated in their own classes (following the existing ECC engine structures).
* Comment any complex mathematical operations or combinatorial logic so other researchers can follow the data flow.
