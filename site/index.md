---
layout: home
title: doorplate
description: Notes on building doorplate, an open-source US address parser in Rust with Python bindings, for real estate and MLS data.
---

[doorplate](https://github.com/jeremeybingham/doorplate) parses US addresses into components, USPS Publication 28 and RESO output, and a stable match key. It does not validate that an address exists or can receive mail.

**[Try it in your browser]({{ '/demo/' | relative_url }})**: type an address and watch doorplate take it apart.

`pip install doorplate` · `cargo add doorplate`
