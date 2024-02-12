# uppy
FTP uploader with minumum overhead and zero extra dependencies

So I'd like a static built website updated as quickly & reliable as possible! How to do that?
We need to know what actually has to be updated instead of just pushing all without
checking. For that we'll download a manifest file containing filenames and hashes for each
target directory. If such file is not yet present all the files are initially
pushed. Then we always just check against a local manifest and sync anything off.

Pros:
 * checks are done super quickly
 * actual update uploads are as compact as possible
 * deletions are handled as well (Of files once uploaded via uppy)
 * any other remote dirs and files are ignored by default

Cons:
 * initially ALL files need to be uploaded (we "could" instead download first
   and update if necessary. TBD)
 * If a file is removed remotely uppy wouldn't notice. (We could do a post-
   check to fix any missing files. TBD)
 * we need to have this remote manifest file (which could potentially be found
   on the server and reveal files and hashes) (we could however obfuscate it at
   least a little.)
 * nothing concurrent yet (we could try downloading the manifest while scanning locally) (currently it all just took split seconds so there was no pressure yet)
