// globally used player_id
let player_id = ''
// for staying in sync with the game this is global
let sync_count = 0
// keep an eye on next player to know if turns are allowed or not
let current_player_id = ''
// lock dragging of cards while waiting for trick being claimed
let cards_locked = false

// show alert messages
function show_message(place, message) {
    $(place).html('<div class="mx-3 mt-3 mb-1 alert alert-danger alert-dismissible dialog-message">' +
        '<a href="#" class="close" data-dismiss="alert" aria-label="close">&times;</a>' +
        message +
        '</div>')
}

function clear_message(place) {
    $(place).html('')
}

function check_sync(msg) {

    console.log(sync_count, msg.sync_count, $('#sync_count').data('sync_count'))

    // check if message is in sync

    // if not set yet take sync_count from freshly loaded HTML id
    if (sync_count == 0) {
        sync_count = $('#sync_count').data('sync_count')
    }
    if ((sync_count + 1 == msg.sync_count) || (sync_count == msg.sync_count)) {
        sync_count = msg.sync_count
        return true
    } else {
        // sync_count won't be persistent anyway because page will be reloaded to make refresh safely work
        // sync_count = msg.sync_count
        if (location.pathname.startsWith('/table/')) {
            location.reload()
        }
        return false
    }
}


$(document).ready(function () {
    // get initial timestamp from table
    // sync_count = $('#sync_count').data('sync_count')

    // initialize SocketIO
    const socket = io()

    // initialize drag&drop
    let dragging_cards = dragula([document.querySelector('#hand'),
        document.querySelector('#table'), {
            revertOnSpill: true,
            direction: 'horizontal'
        }
    ]);
    dragging_cards.on('drop', function (card, target, source) {
        // do not drag your gained tricks around
        if (card.id == 'cards_stack') {
            dragging_cards.cancel(true)
        } else if (source.id == 'hand' && target.id == 'table' && player_id == current_player_id && !cards_locked) {
            if ($(card).data('cards_timestamp') == $('#cards_table_timestamp').data('cards_timestamp')) {
                // only accept card if not too many on table - might happen after reload
                if ($('#table').children('.game-card').length <= 4) {
                    $('#table').append(card)
                    // add tooltip
                    $(card).attr('title', player_id)
                    socket.emit('played-card', {
                        player_id: player_id,
                        card_id: $(card).data('id'),
                        card_name: $(card).data('name'),
                        table_id: $(card).data('table_id')
                    })
                } else {
                    dragging_cards.cancel(true)
                }
            } else {
                // card does not belong to hand because the dealer dealed again while the card was dragged around
                $(card).remove()
            }
        } else if (source.id == 'hand' && target.id == 'hand') {
            // check if card and hand have the same timestamp - otherwise someone dealed new cards
            // and the dragged card does not belong to the current cards
            if ($(card).data('cards_timestamp') == $('#cards_hand_timestamp').data('cards_timestamp')) {
                // get cards order to end it to server for storing it
                let cards_hand_ids = []
                for (let card_hand of $('#hand').children('.game-card-hand')) {
                    cards_hand_ids.push($(card_hand).data('id'))
                }
                socket.emit('sorted-cards', {
                    player_id: player_id,
                    table_id: $(card).data('table_id'),
                    cards_hand_ids: cards_hand_ids
                })
                // to avoid later mess (cards stack inside the cards at hand) move stack to end
                $('#cards_stack').appendTo('#hand')
                return true
            } else {
                // card does not belong to hand because the dealer dealed again while the card was dragged around
                $(card).remove()
            }
        } else if (source.id == 'table' || cards_locked || player_id != current_player_id) {
            dragging_cards.cancel(true)
        }
    })

    //
    // ------------ Socket.io events ------------
    //

    socket.on('connect', function () {
        // revalidate user ID
        socket.emit('who-am-i')
    })

    socket.on('you-are-what-you-is', function (msg) {
        if (player_id == '') {
            player_id = msg.player_id
        }
        if (current_player_id == '') {
            current_player_id = msg.current_player_id
        }
        // check if being still in sync
        check_sync(msg)

        // show results if finished
        if (msg.round_finished) {
            socket.emit('need-final-result', {
                player_id: player_id,
                table_id: msg.table_id
            })
        }
        // check if round is freshly reset - if yes get cards
        if (msg.round_reset) {
            socket.emit('my-cards-please', {
                player_id: player_id,
                table_id: msg.table_id
            })
        }
    })

    socket.on('new-table-available', function (msg) {
        $('#list_tables').html(msg.html)
    })

    socket.on('played-card-by-user', function (msg) {
        if (check_sync(msg)) {
            current_player_id = msg.current_player_id
            $('#hud_players').html(msg.html.hud_players)
            $('.overlay-button').addClass('d-none')

            // either #table_spectator or #table are visible and may show the cards on table
            if ($('#table_spectator').hasClass('d-none')) {
                $('#table').html(msg.html.cards_table)
            } else {
                $('#table_spectator').html(msg.html.cards_table)
                // strange move to take away card by class but not possible by id because it would vanish on table too
                // make sure that even after some lost communication all cards are updated
                // just take away already played cards
                for (let card_id of msg.played_cards) {
                    $('.card_' + card_id).remove()
                }
            }
        }
        if (msg.is_last_turn) {
            cards_locked = true
            $('#turn_indicator').addClass('d-none')
            if (!msg.idle_players.includes(player_id)) {
                $('#button_claim_trick').removeClass('d-none').fadeOut(1).delay(1500).fadeIn(1)
            }
        } else if (msg.cards_shown) {
            cards_locked = true
            $('#turn_indicator').addClass('d-none')
            $('#button_claim_trick').addClass('d-none')
        } else {
            cards_locked = false
            if (player_id == current_player_id) {
                $('#turn_indicator').removeClass('d-none')
            } else {
                $('#turn_indicator').addClass('d-none')
            }
            $('#button_claim_trick').addClass('d-none')
        }
        // anyway there is no need anymore to deal cards
        $('#button_deal_cards_again').addClass('d-none')
    })

    socket.on('grab-your-cards', function (msg) {
        // if (check_sync(msg)) {
        socket.emit('my-cards-please', {
            player_id: player_id,
            table_id: msg.table_id
        })
        // }
    })

    socket.on('your-cards-please', function (msg) {
        current_player_id = msg.current_player_id
        if (check_sync(msg)) {
            if (msg.cards_shown) {
                cards_locked = true
            } else {
                cards_locked = false
            }
            if (player_id == current_player_id && !cards_locked) {
                $('#turn_indicator').removeClass('d-none')
            } else {
                $('#turn_indicator').addClass('d-none')
            }
            if (msg.trick_claiming_needed && !cards_locked) {
                $('#button_claim_trick').removeClass('d-none').fadeOut(1).delay(1500).fadeIn(1)
            } else {
                $('#button_claim_trick').addClass('d-none')
            }
            $('.mode-spectator').addClass('d-none')
            $('.mode-player').removeClass('d-none')
            $('#hud_players').html(msg.html.hud_players)
            $('#table').html(msg.html.cards_table)
            $('#table_spectator').html('')
            $('#hand').html(msg.html.cards_hand)
            $('#button_claim_trick').addClass('d-none')
            $('#modal_dialog').modal('hide')
            if (player_id == msg.dealer && msg.dealing_needed) {
                $('#button_deal_cards_again').removeClass('d-none')
            } else {
                $('#button_deal_cards_again').addClass('d-none')
            }
        }
    })

    socket.on('sorry-no-cards-for-you', function (msg) {
        if (check_sync(msg)) {
            $('#modal_body').html('')
            $("#modal_dialog").modal('hide')
            $('.mode-spectator').removeClass('d-none')
            $('.mode-player').addClass('d-none')
            $('#hud_players').html(msg.html.hud_players)
            $('#table').html('')
            $('#table_spectator').html(msg.html.cards_table)
            $('#hand_spectator_upper').html(msg.html.cards_hand_spectator_upper)
            $('#hand_spectator_lower').html(msg.html.cards_hand_spectator_lower)
        }
    })

    socket.on('really-deal-again', function (msg) {
        if (check_sync(msg)) {
            $('.overlay-notification').addClass('d-none')
            $('#modal_body').html(msg.html)
            $("#modal_dialog").modal('show')
        }
    })

    socket.on('next-trick', function (msg) {
        if (check_sync(msg)) {
            current_player_id = msg.current_player_id
            cards_locked = false
            $('#table').html(msg.html.cards_table)
            if (player_id == current_player_id) {
                $('#turn_indicator').removeClass('d-none')
            } else {
                $('#turn_indicator').addClass('d-none')
            }
            $('#hud_players').html(msg.html.hud_players)
            if (msg.score[player_id] > 0) {
                $('#cards_stack_img').attr('title', msg.score[player_id])
                $('#cards_stack').removeClass('d-none')
            } else {
                $('#cards_stack').addClass('d-none')
            }
        }
    })

    socket.on('round-finished', function (msg) {
        if (check_sync(msg)) {
            $('#button_claim_trick').addClass('d-none')
            // cleanup content of dialog
            $('#modal_body').html(msg.html)
            $("#modal_dialog").modal('show')
        }
    })

    socket.on('start-next-round', function (msg) {
        $('.overlay-button').addClass('d-none')
        $('.overlay-notification').addClass('d-none')
        $('#modal_body').html(msg.html)
        if (player_id == msg.dealer) {
            $('#button_deal_cards').removeClass('d-none')
            $('#button_close_info').addClass('d-none')
        } else {
            $('#button_deal_cards').addClass('d-none')
            $('#button_close_info').removeClass('d-none')
        }
        $("#modal_dialog").modal('show')
    })

    socket.on('round-reset-requested', function (msg) {
        $('.overlay-button').addClass('d-none')
        $('.overlay-notification').addClass('d-none')
        // cleanup content of dialog
        $('#modal_body').html(msg.html)
        $('#modal_dialog').modal('show')
    })

    socket.on('round-finish-requested', function (msg) {
        $('.overlay-button').addClass('d-none')
        $('.overlay-notification').addClass('d-none')
        // cleanup content of dialog
        $('#modal_body').html(msg.html)
        $('#modal_dialog').modal('show')
    })

    socket.on('undo-requested', function (msg) {
        $('.overlay-button').addClass('d-none')
        $('.overlay-notification').addClass('d-none')
        // cleanup content of dialog
        $('#modal_body').html(msg.html)
        $('#modal_dialog').modal('show')
    })

    socket.on('really-show-cards', function (msg) {
        if (check_sync(msg)) {
            $('.overlay-notification').addClass('d-none')
            $('#modal_body').html(msg.html)
            $("#modal_dialog").modal('show')
        }
    })

    socket.on('change-password-successful', function (msg) {
        $('#button_change_password').removeClass('btn-outline-primary')
        $('#button_change_password').removeClass('btn-outline-danger')
        $('#button_change_password').addClass('btn-outline-success')
        $('#indicate_change_password_successful').removeClass('d-none')
        $('#indicate_change_password_failed').addClass('d-none')
        $('#submit_change_password').addClass('d-none')
    })

    socket.on('change-password-failed', function (msg) {
        $('#button_change_password').removeClass('btn-outline-primary')
        $('#button_change_password').removeClass('btn-outline-success')
        $('#button_change_password').addClass('btn-outline-danger')
        $('#indicate_change_password_failed').removeClass('d-none')
        $('#indicate_change_password_successful').addClass('d-none')
        $('#submit_change_password').addClass('d-none')
    })

    socket.on('cards-shown-by-user', function (msg) {
        if (check_sync(msg)) {
            if ($('.mode-spectator').hasClass('d-none')) {
                $('#table').html(msg.html.cards_table)
            } else {
                $('#table_spectator').html(msg.html.cards_table)
            }
            cards_locked = true
            $('#turn_indicator').addClass('d-none')
            $('#button_claim_trick').addClass('d-none')
        }
    })

//
// ------------ Document events ------------
//

    $(document).on('click', '.button-enter-table', function () {
        let table_id = $(this).data('table_id')
        socket.emit('enter-table', {
            player_id: player_id,
            table_id: table_id
        })
        // ask server via json if player is allowed to enter or not
        return $.getJSON('/enter/table/' + encodeURIComponent($(this).data('table_id')) + '/' + encodeURIComponent(player_id),
            function (data, status) {
                if (status == 'success' && data.allowed) {
                    // return data.allowed
                    if (data.allowed) {
                        // use location.assign to avoid browsers decoding the id
                        location.assign('/table/' + encodeURIComponent(table_id))
                    }
                }
                // dummy return just in case
                return false
            })
    })

// set focus onto defined form field
    $('#modal_dialog').on('shown.bs.modal', function () {
        $('.form-focus').focus()
    })

// create new table
    $(document).on('click', '#button_create_table', function () {
        $.getJSON('/create/table', function (data, status) {
            if (status == 'success') {
                $('#modal_body').html(data.html)
                clear_message('#modal_message')
                $('#modal_dialog').modal('show')
            }
        })
        return false
    })

// parameter 'json' makes it equivalent to non-existing .postJSON
    $(document).on('click', '#button_finish_create_table', function () {
        // parameter 'json' makes it equivalent to .getJSON
        // because there is no .postJSON but .post(..., 'json') so it will be the same for GET and POST here
        $.post('/create/table', $('#form_create_table').serialize(), function (data, status) {
            if (status == 'success') {
                if (data.status == 'error') {
                    show_message('#modal_message', data.message)
                } else if (data.status == 'ok') {
                    $('#modal_dialog').modal('hide')
                    $.getJSON('/get/tables',
                        function (data, status) {
                            if (status == 'success') {
                                $('#list_tables').html(data.html)
                            }
                        })
                }
            }
        }, 'json')
        return false
    })

// draggable list of players in setup table dialog
    $(document).on('click', '.setup-table', function () {
        $.getJSON('/setup/table/' + encodeURIComponent($(this).data('table_id')), function (data, status) {
            if (status == 'success' && data.allowed) {
                $("#modal_body").html(data.html)
                $('#modal_dialog').modal('show')
                let dragging_players = dragula([document.querySelector('#setup_table_players'),
                    {
                        revertOnSpill: true,
                        direction: 'vertical'
                    }
                ]);
                dragging_players.on('drop', function (player, target) {
                    // players order has been changed
                    let order = []
                    for (let player of $(target).children('.player')) {
                        order.push($(player).data('player_id'))
                    }
                    socket.emit('setup-table-change', {
                        action: 'changed_order',
                        player_id: player_id,
                        table_id: $(target).data('table_id'),
                        order: order
                    })
                })
            }
        })
        return false
    })

// lock table number of players
    $(document).on('click', '#table_lock', function () {
        if (this.checked) {
            $('#table_lock_icon').removeClass('oi-lock-unlocked')
            $('#table_lock_icon').addClass('oi-lock-locked')
            socket.emit('setup-table-change', {
                action: 'lock_table',
                player_id: player_id,
                table_id: $(this).data('table_id')
            })
        } else {
            $('#table_lock_icon').addClass('oi-lock-unlocked')
            $('#table_lock_icon').removeClass('oi-lock-locked')
            socket.emit('setup-table-change', {
                action: 'unlock_table',
                player_id: player_id,
                table_id: $(this).data('table_id')
            })
        }
    })

// enable playing with card '9'
    $(document).on('click', '#switch_card_9', function () {
        if (this.checked) {
            socket.emit('setup-table-change', {
                action: 'play_with_9',
                player_id: player_id,
                table_id: $(this).data('table_id')
            })
        } else {
            socket.emit('setup-table-change', {
                action: 'play_without_9',
                player_id: player_id,
                table_id: $(this).data('table_id')
            })
        }
    })

// allow undoing a trick when wrong card was played
    $(document).on('click', '#switch_allow_undo', function () {
        if (this.checked) {
            $('#menu_request_undo').removeClass('d-none')
            socket.emit('setup-table-change', {
                action: 'allow_undo',
                player_id: player_id,
                table_id: $(this).data('table_id')
            })
        } else {
            $('#menu_request_undo').addClass('d-none')
            socket.emit('setup-table-change', {
                action: 'prohibit_undo',
                player_id: player_id,
                table_id: $(this).data('table_id')
            })
        }
    })

// enable exchange option
    $(document).on('click', '#switch_allow_exchange', function () {
        if (this.checked) {
            $('#menu_request_exchange').removeClass('d-none')
            socket.emit('setup-table-change', {
                action: 'allow_exchange',
                player_id: player_id,
                table_id: $(this).data('table_id')
            })
        } else {
            $('#menu_request_exchange').addClass('d-none')
            socket.emit('setup-table-change', {
                action: 'prohibit_exchange',
                player_id: player_id,
                table_id: $(this).data('table_id')
            })
        }
    })

// enable debugging if user is admin
    $(document).on('click', '#switch_enable_debugging', function () {
        if (this.checked) {
            socket.emit('setup-table-change', {
                action: 'enable_debugging',
                player_id: player_id,
                table_id: $(this).data('table_id')
            })
        } else {
            socket.emit('setup-table-change', {
                action: 'disable_debugging',
                player_id: player_id,
                table_id: $(this).data('table_id')
            })
        }
    })


// delete a player in the draggable players order
    $(document).on('click', '.button-remove-player-from-table', function () {
        if (player_id != $(this).data('player_id')) {
            // used too if player leaves table via menu
            socket.emit('setup-table-change', {
                action: 'remove_player',
                player_id: $(this).data('player_id'),
                table_id: $(this).data('table_id')
            })
            // id needs to get % escaped
            $('.table_player_' + $(this).data('player_id').replace(/%/g, '\\%')).remove()
        }
    })

// create new user
    $(document).on('click', '#button_create_player', function () {
        $.getJSON('/create/player', function (data, status) {
            if (status == 'success') {
                $('#modal_body').html(data.html)
                clear_message('#modal_message')
                $('#modal_dialog').modal('show')
            }
        })
        return false
    })

// take player id as password
    $(document).on('click', '#button_password_from_player', function () {
        $('#new_player_password').val($('#new_player_id').val())
        return false
    })

// create random password
    $(document).on('click', '#button_password_from_random', function () {
        $('#new_player_password').val(btoa(Math.random()).substr(5, 8))
        return false
    })

// parameter 'json' makes it equivalent to non-existing .postJSON
    $(document).on('click', '#button_finish_create_player', function () {
        // parameter 'json' makes it equivalent to .getJSON
        // because there is no .postJSON but .post(..., 'json') so it will be the same for GET and POST here
        $.post('/create/player', $('#form_create_player').serialize(), function (data, status) {
            if (status == 'success') {
                if (data.status == 'error') {
                    show_message('#modal_message', data.message)
                } else if (data.status == 'ok') {
                    $('#modal_dialog').modal('hide')
                    $.getJSON('/get/players',
                        function (data, status) {
                            if (status == 'success') {
                                $('#list_players').html(data.html)
                            }
                        })
                }
            }
        }, 'json')
        return false
    })

// delete a player in the players list
    $(document).on('click', '.button-delete-player', function () {
        if (player_id != $(this).data('player_id')) {
            $.getJSON('/delete/player/' + encodeURIComponent($(this).data('player_id')),
                function (data, status) {
                    if (status == 'success') {
                        $('#modal_body').html(data.html)
                        clear_message('#modal_message')
                        $('#modal_dialog').modal('show')
                    }
                })
        }
    })

// really delete player after safety dialog
    $(document).on('click', '#button_really_delete_player', function () {
        if (player_id != $(this).data('player_id')) {
            // once again the .post + 'json' move
            $.post('/delete/player/' + encodeURIComponent($(this).data('player_id')),
                function (data, status) {
                    if (status == 'success') {
                        if (data.status == 'ok') {
                            $('#list_players').html(data.html)
                            $('#modal_dialog').modal('hide')
                        } else {
                            $('#modal_body').html(data.html)
                            clear_message('#modal_message')
                            $('#modal_dialog').modal('show')
                        }
                    }
                }, 'json')
        }
        return false
    })

// delete a player in the players list
    $(document).on('click', '.button-delete-table', function () {
        $.getJSON('/delete/table/' + encodeURIComponent($(this).data('table_id')),
            function (data, status) {
                if (status == 'success') {
                    $('#modal_body').html(data.html)
                    clear_message('#modal_message')
                    $('#modal_dialog').modal('show')
                }
            })
    })

// really delete table after safety dialog
    $(document).on('click', '#button_really_delete_table', function () {
        // once again the .post + 'json' move
        $.post('/delete/table/' + encodeURIComponent($(this).data('table_id')),
            function (data, status) {
                if (status == 'success') {
                    if (data.status == 'ok') {
                        $('#list_tables').html(data.html)
                        $('#modal_dialog').modal('hide')
                    } else {
                        $('#modal_body').html(data.html)
                        clear_message('#modal_message')
                        $('#modal_dialog').modal('show')
                    }
                }
            }, 'json')

        return false
    })

    $(document).on('click', '#button_deal_cards', function () {
        socket.emit('deal-cards', {
            player_id: player_id,
            table_id: $(this).data('table_id')
        })
    })

    $(document).on('click', '#button_start_table', function () {
        $.getJSON('/start/table/' + encodeURIComponent($(this).data('table_id')),
            function (data, status) {
                if (status == 'success') {
                    $('#modal_body').html(data.html)
                    clear_message('#modal_message')
                    $('#modal_dialog').modal('show')
                }
            })
        return false
    })

    $(document).on('click', '#button_really_start_table', function () {
        $('#modal_dialog').modal('hide')
        socket.emit('setup-table-change', {
            action: 'start_table',
            player_id: player_id,
            table_id: $(this).data('table_id')
        })
        if (location.pathname.startsWith('/table/')) {
            location.reload()
        }
        return false
    })

// reload page after setup
    $(document).on('click', '#button_finish_table_setup', function () {
        if (!location.pathname.startsWith('/table/')) {
            $.getJSON('/get/tables',
                function (data, status) {
                    if (status == 'success') {
                        $('#list_tables').html(data.html)
                    }
                })
        }
    })

// player setup
    $(document).on('click', '.setup-player', function () {
        $.getJSON('/setup/player/' + encodeURIComponent($(this).data('player_id')), function (data, status) {
            if (status == 'success') {
                $("#modal_body").html(data.html)
                $('#modal_dialog').modal('show')
            }
        })
    })

// change password
    $(document).on('click', '#button_change_password', function () {
        socket.emit('setup-player-change', {
            action: 'new_password',
            player_id: $(this).data('player_id'),
            password: $('#new_player_password').val()
        })
    })

// reset password change button when password gets changed
    $(document).on('keyup', '#new_player_password', function () {
        $('#button_change_password').addClass('btn-outline-primary')
        $('#button_change_password').removeClass('btn-outline-success')
        $('#button_change_password').removeClass('btn-outline-danger')
        $('#submit_change_password').removeClass('d-none')
        $('#indicate_change_password_successful').addClass('d-none')
        $('#indicate_change_password_failed').addClass('d-none')
    })

// make player an admin
    $(document).on('click', '#switch_player_is_admin', function () {
        if (this.checked) {
            socket.emit('setup-player-change', {
                action: 'is_admin',
                player_id: $(this).data('player_id')
            })
        } else {
            socket.emit('setup-player-change', {
                action: 'is_no_admin',
                player_id: $(this).data('player_id')
            })
        }
    })

// let player allow spectators
    $(document).on('click', '#switch_player_allows_spectators', function () {
        if (this.checked) {
            socket.emit('setup-player-change', {
                action: 'allows_spectators',
                player_id: $(this).data('player_id')
            })
        } else {
            socket.emit('setup-player-change', {
                action: 'denies_spectators',
                player_id: $(this).data('player_id')
            })
        }
    })

    $(document).on('click', '#button_deal_cards_again', function () {
        socket.emit('deal-cards-again', {
            player_id: player_id,
            table_id: $(this).data('table_id')
        })
    })

    $(document).on('click', '#button_claim_trick', function () {
        socket.emit('claim-trick', {
            player_id: player_id,
            table_id: $(this).data('table_id')
        })
    })

    $(document).on('click', '#button_next_round', function () {
        socket.emit('ready-for-next-round', {
            player_id: player_id,
            table_id: $(this).data('table_id')
        })
    })

    $(document).on('click', '#menu_request_round_reset', function () {
        socket.emit('request-round-reset', {
            player_id: player_id,
            table_id: $(this).data('table_id')
        })
    })

    $(document).on('click', '#button_round_reset_yes', function () {
        let table_id = $(this).data('table_id')
        $.getJSON('/get/wait', function (data, status) {
            if (status == 'success') {
                $('#modal_body').html(data.html)
                socket.emit('ready-for-round-reset', {
                    player_id: player_id,
                    table_id: table_id
                })
            }
        })
        // dummy return just in case
        return false
    })

    $(document).on('click', '#menu_request_round_finish', function () {
        socket.emit('request-round-finish', {
            player_id: player_id,
            table_id: $(this).data('table_id')
        })
    })

    $(document).on('click', '#button_round_finish_yes', function () {
        let table_id = $(this).data('table_id')
        $.getJSON('/get/wait', function (data, status) {
            if (status == 'success') {
                $('#modal_body').html(data.html)
                socket.emit('ready-for-round-finish', {
                    player_id: player_id,
                    table_id: table_id
                })
            }
        })
        // dummy return just in case
        return false
    })

    $(document).on('click', '#menu_request_undo', function () {
        socket.emit('request-undo', {
            player_id: player_id,
            table_id: $(this).data('table_id')
        })
    })

    $(document).on('click', '#button_undo_yes', function () {
        let table_id = $(this).data('table_id')
        $.getJSON('/get/wait', function (data, status) {
            if (status == 'success') {
                $('#modal_body').html(data.html)
                socket.emit('ready-for-undo', {
                    player_id: player_id,
                    table_id: table_id
                })
            }
        })
        // dummy return just in case
        return false
    })

    $(document).on('click', '#menu_request_show_hand', function () {
        socket.emit('request-show-hand', {
            player_id: player_id,
            table_id: $(this).data('table_id')
        })
    })

    $(document).on('click', '#button_show_cards', function () {
        socket.emit('show-cards', {
            player_id: player_id,
            table_id: $(this).data('table_id')
        })
    })

    $(document).on('click', '#menu_request_exchange', function () {
        socket.emit('request-exchange', {
            player_id: player_id,
            table_id: $(this).data('table_id')
        })
    })
})