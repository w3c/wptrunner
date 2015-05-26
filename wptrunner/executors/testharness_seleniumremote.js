/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/. */

var callback = arguments[arguments.length - 1];
var node_id = "__testharness__results__";

function done() {
    callback(document.getElementById(node_id).textContent);
}

if (document.getElementById(node_id) !== null) {
    done();
} else {
    add_completion_callback(function () {
        add_completion_callback(function() {
            done();
        })
    });
}
