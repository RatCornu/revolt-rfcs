- Feature Name: LDAP
- Start Date: 24/06/2024
- Status: draft

# Summary

Revolt should support a LDAP provider for new users as it is a generic and widely used protocol for user authentication. Users stored in a LDAP connected to Revolt may directly login without prior signing up. Such users will have they password directly checked from the LDAP and not from Revolt's database.

# Motivation

This RFC aims to improve Revolt compatibility with standard authentication protocols by beginning with one of the most used one : LDAP. Thus, it will encourage more people, in particular server administrators, to be interested in Revolt and to host a Revolt server as it will be very convenient for the users that won't need to manage several accounts accross the same server.

# Guide-level explanation

LDAP is a complex protocol so there will not be a full explaination of how it works here. You can look at [the Wikipedia article](https://en.wikipedia.org/wiki/Lightweight_Directory_Access_Protocol) for an introduction, and [the complete RFC of the LDAP3 protocol](https://datatracker.ietf.org/doc/html/rfc4511) if needed. To sum it up briefly, here is the minimal knowledge to understand:

- An *LDAP server* (or LDAP) has a tree-like structure where nodes are called *entries*.
- An *entry* consists of a set of attributes.
- An *attribute* has a name (an attribute type or attribute description) and one or more values. The attributes are defined in a schema (see below).
- Each entry has a unique identifier: its *Distinguished Name* (DN). This consists of its Relative Distinguished Name (RDN), constructed from some attribute(s) in the entry, followed by the parent entry's DN. Think of the DN as the full file path and the RDN as its relative filename in its parent folder (e.g. if /foo/bar/myfile.txt were the DN, then myfile.txt would be the RDN).

Let's take a simple example here on what we could find:

```txt
dc=example,dc=org
├── ou=users
│   ├── cn=alice
│   ├── cn=bob
│   └── cn=charlie
└── ou=groups
    ├── cn=revolt
    └── cn=music
```

Here, there are three users, Alice, Bob and Charlie, and two groups, Revolt and Music. Here's Alice full entry:

```txt
dn: cn=alice,ou=users,dc=example,dc=org
objectClass: inetOrgPerson
cn: alice
mail: alice@example.org
sn: Alice
userPassword: {SSHA}<hashed password>
```

and here's Revolt's:

```txt
dn: cn=revolt,ou=groups,dc=example,dc=org
objectClass: groupOfNames
cn: revolt
member: cn=alice,ou=users,dc=example,dc=org
member: cn=bob,ou=users,dc=example,dc=org
```

As you can see, Alice and Bob are both members of the group "Revolt", but Charlie is not. The goal here is to allow all the members of the Revolt group to be able to login without creating an account on Revolt beforehand: Revolt will read the LDAP to check if a user with the given username, in the Revolt group and with the right password exists.

LDAP is very generic, so in this case the field for the username is `cn`, the one to check the membership is `member` and the one for the password is `userPassword`, but other names are possible (within defined constraints): the full LDAP requests (see below) will be given by the server administrators. Furthermore, to perform LDAP requests, it can either be directly read from the LDAP if it allows to, but in general it will requires to *bind* (authentication) to the LDAP, in which case a node and a password are required.

Once a LDAP user has logged in for the first time, its account will be created at the same time, but its password (even hashed) won't be stored: at each login, the Revolt backend will have to test the password by asking the LDAP server and not with internal methods. For such users, they won't be able to change their password directly from Revolt.

With this architecture, all the requests made to the LDAP server are read-only.

# Reference-level explanation

*We keep here the same example as the section above.*

## LDAP variables

New fields for the `.env` file will be added:

- `LDAP_ENABLED`: a boolean indicating whether LDAP support is enabled on this server
- `LDAP_URI`: a string containing the URI of the LDAP server
- `LDAP_START_TLS`: a boolean indicating whether to enable STARTTLS or not
- `LDAP_BASE_DN`: a string containing the distinguished name of the node that will be taken as the root for the searches
- `LDAP_BIND_DN`: a string containing the distinguished name of the node used to bind or schema to it
- `LDAP_BIND_PASSWORD`: a string containing the password used to bind with the node declared in `LDAP_BIND_DN`
- `LDAP_FIELD_USERNAME`: a string containing the name of the field containing the username of the user
- `LDAP_FIELD_MAIL`: a string containing the name of the field containing the mail of the user
- `LDAP_USER_FILTER`: a string containing the search filter for users

Here is an example of a possible configuration:

```txt
LDAP_ENABLED=true
LDAP_URL="ldaps://example.org:636"
LDAP_START_TLS=true
LDAP_BASE_DN="dc=example,dc=org"
LDAP_BIND_DN="cn=admin,dc=example,dc=org"
LDAP_BIND_PASSWORD="<cn=admin,dc=example,dc=org password>"
LDAP_FIELD_USERNAME="cn"
LDAP_FIELD_MAIL="mail"
LDAP_USER_FILTER="(&(objectClass=inetOrgPerson)(memberOf=cn=revolt,ou=groups,dc=example,dc=org))"
```

As it is also possible to bind directly from a user, the field `LDAP_BIND_DN` can use the parameter "{{username}}" that will automatically be replaced with the given username. In such case, the `LDAP_BIND_PASSWORD` will not be read and the bind password will be the given password. For example, if the configuration is such like:

```txt
LDAP_BIND_DN="cn={{username}},ou=users,dc=example,dc=org"
```

and if Alice tries to login with `alice` as username and `alice_pwd` as password, the bind request to the LDAP will be `cn=alice,ou=users,dc=example,dc=org` for the bind DN, and `alice_pwd` for the bind password.

Moreover, if no bind DN is provided, the requests will be made using anonymous bind.

## User authentication flow

A new `origin` string field will be added to the User object, indicating where the user is located. For now the only possible values would be "revolt" and "ldap:..." (see below), but this would allow further development (as OIDC for example).

For new users that will create an account directly on Revolt, the behavior will not change, and the `origin` field will be set as "revolt".

For users that have an LDAP account and that are caught in the user filter (see `LDAP_USER_FILTER` above), they will be able to connect without an account creation, and their mail, directly read in the LDAP (at the field `LDAP_FIELD_MAIL`), is directly considered as verified. On the first login, a user corresponding to the LDAP user will be created in the Revolt database, with the field `origin` set as "ldap:<distinguished name of the user LDAP entry>".

All the user authentications will proceed as follow: with the given username and password, look in the Revolt database to see if a user with the given username exists:

- if it exists, look at the user's `origin` field in the database:

   - if it is equal to "revolt", try to authenticate the user with the given password using Revolt database;

   - if it is equal to "ldap:<user DN>", try to bind to the LDAP user with a DN equal to <user DN>, and the given password.

- if not, look at the LDAP server to see if a user with the given username and in the user filter exists:

   - if it exists, it means that this is the first time login of this user: create an account as described above, then go back to the "user exists in the database" case;

   - if it does not exist, the authentication has failed.

# Drawbacks

As the use of LDAP is entirely optional for server administrators, there is no real drawback to this RFC.

# Rationale and alternatives

This implementation of the LDAP protocol is simple as all the queries are read-only. The counterpart is that LDAP users won't be able to directly change their password or their mail. If the user origin is LDAP, an environment variable and a button could be added to redirect them to a page where they can do so (as in Jellyfin LDAP-Auth Plugin, see below).

Another possibility would be to only support the modification of some LDAP field, in particular `userPassword`. This would allow users to directly change their password within Revolt (as in authentik, see below).

# Prior art

LDAP has been implemented on a very huge number of softwares, such as :

- [Nextcloud's LDAP built-in application](https://docs.nextcloud.com/server/latest/admin_manual/configuration_user/user_auth_ldap.html)
- [Matrix Synapse LDAP Auth Provider](https://github.com/matrix-org/matrix-synapse-ldap3)
- [Jellyfin LDAP-Auth Plugin](https://github.com/jellyfin/jellyfin-plugin-ldapauth)
- [authentik](https://goauthentik.io/)

I don't know any big Rust project using LDAP.

# Security concerns

As this RFC enables the communication between Revolt and the LDAP protocol, a breach could be find in the implementation of the LDAP client used for the implementation to obtain information about the LDAP server. This does not directly depend on Revolt's backend so it should not be a major threat if a serious library is taken for the implementation of this RFC.

# Future ideas

This RFC would be the first allowing external authentication. Other standard protocols could be implemented in the future, namely Oauth2/OIDC (in priority), or SAML.
