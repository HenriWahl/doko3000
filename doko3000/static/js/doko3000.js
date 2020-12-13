// globally used player_id
let player_id = ''
// for staying in sync with the game this is global
let sync_count = 0
// keep an eye on next player to know if turns are allowed or not
let current_player_id = ''
// lock dragging of cards while waiting for trick being claimed
let cards_locked = false
// table mode, might be normal or exchange
let table_mode = 'normal'
// minimum cards to be exchanged - only interesting for player2, who has to return the same amount of cards as given
let exchange_min_cards = 1
// maximum number of cards to exchange - for player2 depends on number of cards given by player1
let exchange_max_cards = 3


// show alert messages
function show_message(place, message) {
    $('#modal_message').html('<div class="mx-3 mt-3 mb-1 alert alert-danger alert-dismissible dialog-message">' +
        '<a href="#" class="close" data-dismiss="alert" aria-label="close">&times;</a>' +
        message +
        '</div>')
}

// show modal dialog and fill it with content
function show_dialog(html) {
    $('#modal_body').html(html)
    $('#modal_message').html('')
    $("#modal_dialog").modal('show')
}

// check if message is in sync
function check_sync(msg) {
    // if not set yet take sync_count from freshly loaded HTML id
    console.log(sync_count)
    if (sync_count == 0) {
        sync_count = $('#sync_count').data('sync_count')
    }
    if ((sync_count + 1 == msg.sync_count) || (sync_count == msg.sync_count)) {
        sync_count = msg.sync_count
        return true
    } else {
        // sync_count won't be persistent anyway because page will be reloaded to make refresh safely work
        if (location.pathname.startsWith('/table/')) {
            location.reload()
        }
        return false
    }
}


$(document).ready(function () {
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
            // get cards order to send it to server for storing or checking it
            let cards_hand_ids = []
            for (let card_hand of $('#hand').children('.game-card-hand')) {
                cards_hand_ids.push($(card_hand).data('id'))
            }
            // do not drag your gained tricks around
            if (card.id == 'cards_stack') {
                dragging_cards.cancel(true)
            }
            // 'normal' is not-currently-exchanging - quite normal
            if (table_mode == 'normal') {
                if (source.id == 'hand' && target.id == 'table' && player_id == current_player_id && !cards_locked) {
                    if ($(card).data('cards_timestamp') == $('#cards_table_timestamp').data('cards_timestamp')) {
                        // only accept card if not too many on table - might happen after reload
                        if ($('#table').children('.game-card').length <= 4) {
                            $('#table').append(card)
                            // add tooltip
                            $(card).attr('title', player_id)
                            socket.emit('card-played', {
                                player_id: player_id,
                                card_id: $(card).data('id'),
                                card_name: $(card).data('name'),
                                table_id: $(card).data('table_id'),
                                cards_hand_ids: cards_hand_ids
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
                        socket.emit('sorted-cards', {
                            player_id: player_id,
                            table_id: $(card).data('table_id'),
                            cards_hand_ids: cards_hand_ids
                        })
                        // to avoid later mess (cards stack inside the cards at hand) move stack to end
                        $('#cards_stack').appendTo('#hand')
                        return true
                    } else if (card.id == 'cards_stack') {
                        // do not drag your gained tricks around
                        dragging_cards.cancel(true)
                    } else {
                        // card does not belong to hand because the dealer dealed again while the card was dragged around
                        $(card).remove()
                    }
                } else if (source.id == 'table' || cards_locked || player_id != current_player_id) {
                    dragging_cards.cancel(true)
                }
            } else if (table_mode == 'exchange') {
                if ($(card).data('cards_timestamp') == $('#cards_table_timestamp').data('cards_timestamp')) {
                    // only accept maximum of 3 cards
                    if ($('#table').children('.game-card').length <= exchange_max_cards && !cards_locked) {
                        // get cards order to end it to server for storing it
                        let cards_hand_ids = []
                        for (let card_hand of $('#hand').children('.game-card-hand')) {
                            cards_hand_ids.push($(card_hand).data('id'))
                        }
                        let cards_table_ids = []
                        for (let card_table of $('#table').children('.game-card')) {
                            cards_table_ids.push($(card_table).data('id'))
                        }
                        socket.emit('card-exchanged', {
                            player_id: player_id,
                            table_id: $(card).data('table_id'),
                            cards_hand_ids: cards_hand_ids,
                            cards_table_ids: cards_table_ids
                        })
                    } else {
                        // no more cards than 3
                        dragging_cards.cancel(true)
                    }
                } else {
                    // no draggin' and droppin' if cards are locked due to waiting for peer's cards
                    dragging_cards.cancel(true)
                }
            }
        })

        // if there are no tables or not enough players in round show welcome messages
        if ($('#needs_welcome').data('state')) {
            if ($('#needs_welcome').data('table_id') != undefined) {
                let table_id = $('#needs_welcome').data('table_id')
                $.getJSON('/get/welcome/' + encodeURIComponent(table_id), function (data, status) {
                    if (status == 'success') {
                        // $('#modal_body').html(data.html)
                        // clear_message('#modal_message')
                        // $("#modal_dialog").modal('show')
                        show_dialog(data.html)
                    }
                })
            } else {
                $.getJSON('/get/welcome', function (data, status) {
                        if (status == 'success') {
                            // $('#modal_body').html(data.html)
                            // clear_message('#modal_message')
                            // $("#modal_dialog").modal('show')
                            show_dialog(data.html)
                        }
                    }
                )
            }
        }
//
// ------------ Socket.io events ------------
//

        // ask server about me and the game when connecting
        socket.on('connect', function () {
            // revalidate user ID
            socket.emit('who-am-i')
        })

        // answer on 'who-am-i'
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

        // update tables list due to new table being created
        socket.on('new-table-available', function (msg) {
            $('#list_tables').html(msg.html)
        })

        // broadcasted to every player at the table
        socket.on('card-played-by-player', function (msg) {
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
                if (!msg.idle_players.includes(player_id) && !msg.players_spectator.includes(player_id)) {
                    $('#button_claim_trick').removeClass('d-none').fadeOut(1).delay(1500).fadeIn(1)
                }
            } else if (msg.player_showing_cards) {
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

        // told to every player of current round to ask for cards
        socket.on('grab-your-cards', function (msg) {
            socket.emit('my-cards-please', {
                player_id: player_id,
                table_id: msg.table_id
            })
        })

        // answer to my-cards-please
        socket.on('your-cards-please', function (msg) {
            current_player_id = msg.current_player_id
            if (check_sync(msg)) {
                if (msg.player_showing_cards) {
                    cards_locked = true
                } else {
                    cards_locked = false
                }
                if (player_id == current_player_id && !cards_locked && !msg.exchange_needed) {
                    $('#turn_indicator').removeClass('d-none')
                } else {
                    $('#turn_indicator').addClass('d-none')
                }
                if (msg.exchange_needed) {
                    $('#button_exchange_send_cards').removeClass('d-none')
                    table_mode = 'exchange'
                } else {
                    $('#button_exchange_send_cards').addClass('d-none')
                    table_mode = 'normal'
                }
                if (msg.needs_trick_claiming && !cards_locked) {
                    $('#button_claim_trick').removeClass('d-none').fadeOut(1).delay(1500).fadeIn(1)
                } else {
                    $('#button_claim_trick').addClass('d-none')
                }
                $('.mode-spectator').addClass('d-none')
                $('.mode-player').removeClass('d-none')
                $('#hud_players').html(msg.html.hud_players)
                $('#table').html(msg.html.cards_table)
                $('#table_spectator').html('')
                $('#hand').html('')
                $('#hand').html(msg.html.cards_hand)
                $('#button_claim_trick').addClass('d-none')
                $('#modal_dialog').modal('hide')
                if (player_id == msg.dealer && msg.needs_dealing && !msg.exchange_needed) {
                    $('#button_deal_cards_again').removeClass('d-none')
                } else {
                    $('#button_deal_cards_again').addClass('d-none')
                }
                // a true miracle which can't be repeated once led to 13 cards on player's hand
                // instead of 12 - this measure should avoid it by just reloading after
                // checking if number of cards in hand matches the correct number
                if (msg.cards_per_player != $('#hand').children('.game-card-hand').length) {
                    socket.emit('my-cards-please', {
                        player_id: player_id,
                        table_id: msg.table_id
                    })
                }
            }
        })

        // anser to my-cards-please if player is only spectator
        socket.on('sorry-no-cards-for-you', function (msg) {
            if (check_sync(msg)) {
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

        // click on deal-again-button
        socket.on('confirm-deal-again', function (msg) {
            if (check_sync(msg)) {
                $('.overlay-notification').addClass('d-none')
                // $('#modal_body').html(msg.html)
                // $("#modal_dialog").modal('show')
                show_dialog(msg.html)
            }
        })

        // sent after someone claimed a trick
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

        // sent at the end of a round
        socket.on('round-finished', function (msg) {
            if (check_sync(msg)) {
                $('#button_claim_trick').addClass('d-none')
                // cleanup content of dialog
                // $('#modal_body').html(msg.html)
                // $("#modal_dialog").modal('show')
                show_dialog(msg.html)
            }
        })

        // tells players the next round is beginning
        socket.on('start-next-round', function (msg) {
            $('.overlay-button').addClass('d-none')
            $('.overlay-notification').addClass('d-none')
            // dialog has to be shown before buttons are treated
            show_dialog(msg.html)
            if (player_id == msg.dealer) {
                $('#button_deal_cards').removeClass('d-none')
                $('#button_close_info').addClass('d-none')
            } else {
                $('#button_deal_cards').addClass('d-none')
                $('#button_close_info').removeClass('d-none')
            }

        })

        // sent on requested round reset
        socket.on('round-reset-requested', function (msg) {
            $('.overlay-button').addClass('d-none')
            $('.overlay-notification').addClass('d-none')
            // cleanup content of dialog
            // $('#modal_body').html(msg.html)
            // $('#modal_dialog').modal('show')
            show_dialog(msg.html)
        })

        // sent on requested round finish
        socket.on('round-finish-requested', function (msg) {
            $('.overlay-button').addClass('d-none')
            $('.overlay-notification').addClass('d-none')
            // cleanup content of dialog
            // $('#modal_body').html(msg.html)
            // $('#modal_dialog').modal('show')
            show_dialog(msg.html)
        })

        // sent if undo was requested
        socket.on('undo-requested', function (msg) {
            $('.overlay-button').addClass('d-none')
            $('.overlay-notification').addClass('d-none')
            // cleanup content of dialog
            // $('#modal_body').html(msg.html)
            // $('#modal_dialog').modal('show')
            show_dialog(msg.html)
        })

        // if player wants to show cards confirm it
        socket.on('confirm-show-cards', function (msg) {
            if (check_sync(msg)) {
                $('.overlay-notification').addClass('d-none')
                // $('#modal_body').html(msg.html)
                // $("#modal_dialog").modal('show')
                show_dialog(msg.html)
            }
        })

        // intended exchange is about to be confirmed
        socket.on('confirm-exchange', function (msg) {
            if (check_sync(msg)) {
                $('.overlay-notification').addClass('d-none')
                // there is no need anymore to deal cards
                $('#button_deal_cards_again').addClass('d-none')
                // $('#modal_body').html(msg.html)
                // $("#modal_dialog").modal('show')
                show_dialog(msg.html)
            }
        })

        // received if password was changed
        socket.on('change-password-successful', function (msg) {
            $('#button_change_password').removeClass('btn-primary')
            $('#button_change_password').removeClass('btn-danger')
            $('#button_change_password').addClass('btn-success')
            $('#indicate_change_password_successful').removeClass('d-none')
            $('#indicate_change_password_failed').addClass('d-none')
            $('#submit_change_password').addClass('d-none')
        })

        // received if password was NOT changed
        socket.on('change-password-failed', function (msg) {
            $('#button_change_password').removeClass('btn-primary')
            $('#button_change_password').removeClass('btn-success')
            $('#button_change_password').addClass('btn-danger')
            $('#indicate_change_password_failed').removeClass('d-none')
            $('#indicate_change_password_successful').addClass('d-none')
            $('#submit_change_password').addClass('d-none')
        })

        // show cards of a player on request
        socket.on('cards-shown-by-player', function (msg) {
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

        // peer of a player gets asked if exchange is wanted
        socket.on('exchange-ask-player2', function (msg) {
            if (check_sync(msg)) {
                $('.overlay-notification').addClass('d-none')
                // there is no need anymore to deal cards
                $('#button_deal_cards_again').addClass('d-none')
                // $('#modal_body').html(msg.html)
                // $("#modal_dialog").modal('show')
                show_dialog(msg.html)
            }
        })

        // player 2 doesn't want to exchange cards with player1
        socket.on('exchange-player1-player2-deny', function (msg) {
            if (check_sync(msg)) {
                $('.overlay-notification').addClass('d-none')
                // $('#modal_body').html(msg.html)
                // $("#modal_dialog").modal('show')
                show_dialog(msg.html)
            }
        })

        // player1 shall start card exchange
        socket.on('exchange-player1-start', function (msg) {
            $('.overlay-notification').addClass('d-none')
            $('#button_exchange_send_cards').removeClass('d-none')
            table_mode = 'exchange'
            cards_locked = false
        })

        // exchanged cards arrive at exchanging peer
        socket.on('exchange-player-cards-to-client', function (msg) {
            $('.overlay-notification').addClass('d-none')
            if (msg.table_mode == 'exchange') {
                $('#button_exchange_send_cards').removeClass('d-none')
                table_mode = msg.table_mode
                exchange_min_cards = msg.cards_exchange_count
                exchange_max_cards = msg.cards_exchange_count
            } else {
                table_mode = msg.table_mode
            }
            $('#hand').html(msg.html.cards_hand)
            cards_locked = false
            // }
        })

        // tell everybody that the exchange is finally starting, so no new cards should be dealed or put onto table
        socket.on('exchange-players-starting', function (msg) {
            $('#turn_indicator').addClass('d-none')
            $('#button_deal_cards_again').addClass('d-none')
            cards_locked = true
        })

        // tell everybody that the exchange is finally finished
        socket.on('exchange-players-finished', function (msg) {
            current_player_id = msg.current_player_id
            cards_locked = false
            table_mode = 'normal'
            if (player_id == current_player_id && !cards_locked) {
                $('#turn_indicator').removeClass('d-none')
            } else {
                $('#turn_indicator').addClass('d-none')
            }
            // spectator shall see the refreshed exchanged cards
            if (!$('.mode-spectator').hasClass('d-none')) {
                socket.emit('my-cards-please', {
                    player_id: player_id,
                    table_id: msg.table_id
                })
            }
        })

        // update either list of tables or users after a change
        socket.on('index-list-changed', function (msg) {
            if (!location.pathname.startsWith('/table/')) {
                $.getJSON('/get/' + msg.table,
                    function (data, status) {
                        if (status == 'success') {
                            $('#list_' + msg.table).html(data.html)
                        }
                    })
            }
        })

//
// ------------ Document events ------------
//

        // player enters table
        $(document).on('click', '.button-enter-table', function () {
            let table_id = $(this).data('table_id')
            socket.emit('enter-table', {
                player_id: player_id,
                table_id: table_id
            })
            // ask server via json if player is allowed to enter or not
            return $.getJSON('/enter/table/' + encodeURIComponent(table_id) + '/' + encodeURIComponent(player_id),
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
                    // $('#modal_body').html(data.html)
                    // clear_message('#modal_message')
                    // $('#modal_dialog').modal('show')
                    show_dialog(data.html)
                }
            })
            return false
        })

        // table will be created
        $(document).on('click', '#button_finish_create_table', function () {
            // parameter 'json' makes it equivalent to .getJSON
            // because there is no .postJSON but .post(..., 'json') so it will be the same for GET and POST here
            $.post('/create/table', $('#form_create_table').serialize(), function (data, status) {
                if (status == 'success') {
                    if (data.status == 'error') {
                        show_message('#modal_message', data.message)
                    } else if (data.status == 'ok') {
                        $('#modal_dialog').modal('hide')
                        socket.emit('setup-table-change', {
                            action: 'finished',
                            player_id: player_id
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
                    // $("#modal_body").html(data.html)
                    // $('#modal_dialog').modal('show')
                    show_dialog(data.html)
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
                    // $('#modal_body').html(data.html)
                    // clear_message('#modal_message')
                    // $('#modal_dialog').modal('show')
                    show_dialog(data.html)
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
                            // $('#modal_body').html(data.html)
                            // clear_message('#modal_message')
                            // $('#modal_dialog').modal('show')
                            show_dialog(data.html)
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
                                // $('#list_players').html(data.html)
                                $('#modal_dialog').modal('hide')
                                // tell other admins about player changes
                                socket.emit('setup-player-change', {
                                    action: 'finished',
                                    player_id: player_id
                                })
                            } else {
                                // $('#modal_body').html(data.html)
                                // clear_message('#modal_message')
                                // $('#modal_dialog').modal('show')
                                show_dialog(data.html)
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
                        // $('#modal_body').html(data.html)
                        // clear_message('#modal_message')
                        // $('#modal_dialog').modal('show')
                        show_dialog(data.html)
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
                            // $('#list_tables').html(data.html)
                            $('#modal_dialog').modal('hide')
                            // reload tables list everywhere
                            socket.emit('setup-table-change', {
                                action: 'finished',
                                player_id: player_id
                            })
                        } else {
                            // $('#modal_body').html(data.html)
                            // clear_message('#modal_message')
                            // $('#modal_dialog').modal('show')
                            show_dialog(data.html)
                        }
                    }
                }, 'json')

            return false
        })

        // start next round by dealing new cards
        $(document).on('click', '#button_deal_cards', function () {
            socket.emit('deal-cards', {
                player_id: player_id,
                table_id: $(this).data('table_id')
            })
        })

        // table settings button starts table with new settings
        $(document).on('click', '#button_start_table', function () {
            $.getJSON('/start/table/' + encodeURIComponent($(this).data('table_id')),
                function (data, status) {
                    if (status == 'success') {
                        // $('#modal_body').html(data.html)
                        // clear_message('#modal_message')
                        // $('#modal_dialog').modal('show')
                        show_dialog(data.html)
                    }
                })
            return false
        })

        // start table button needs confirmation
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

        // tell everybody there were changes in table setup
        $(document).on('click', '#button_finish_table_setup', function () {
            socket.emit('setup-table-change', {
                action: 'finished',
                player_id: player_id,
                table_id: $(this).data('table_id')
            })
        })

        // player setup
        $(document).on('click', '.setup-player', function () {
            $.getJSON('/setup/player/' + encodeURIComponent($(this).data('player_id')), function (data, status) {
                if (status == 'success') {
                    // $("#modal_body").html(data.html)
                    // clear_message('#modal_message')
                    // $('#modal_dialog').modal('show')
                    show_dialog(data.html)
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
            $('#button_change_password').addClass('btn-primary')
            $('#button_change_password').removeClass('btn-success')
            $('#button_change_password').removeClass('btn-danger')
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

        // let player be spectator only
        $(document).on('click', '#switch_player_is_spectator_only', function () {
            if (this.checked) {
                socket.emit('setup-player-change', {
                    action: 'is_spectator_only',
                    player_id: $(this).data('player_id')
                })
            } else {
                socket.emit('setup-player-change', {
                    action: 'not_is_spectator_only',
                    player_id: $(this).data('player_id')
                })
            }
        })

        // tell everybody there were changes in player setup
        $(document).on('click', '#button_finish_player_setup', function () {
            socket.emit('setup-player-change', {
                action: 'finished',
                player_id: player_id
            })
        })

        // repeat dealing of cards
        $(document).on('click', '#button_deal_cards_again', function () {
            socket.emit('deal-cards-again', {
                player_id: player_id,
                table_id: $(this).data('table_id')
            })
        })

        // pressed big green button to claim trick
        $(document).on('click', '#button_claim_trick', function () {
            socket.emit('claim-trick', {
                player_id: player_id,
                table_id: $(this).data('table_id')
            })
        })

        // player is ready for the next round
        $(document).on('click', '#button_next_round', function () {
            socket.emit('ready-for-next-round', {
                player_id: player_id,
                table_id: $(this).data('table_id')
            })
        })

        // round reset was requested by hamburger menu
        $(document).on('click', '#menu_request_round_reset', function () {
            socket.emit('request-round-reset', {
                player_id: player_id,
                table_id: $(this).data('table_id')
            })
        })

        // confirmed round reset
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

        // round finish requested
        $(document).on('click', '#menu_request_round_finish', function () {
            socket.emit('request-round-finish', {
                player_id: player_id,
                table_id: $(this).data('table_id')
            })
        })

        // round finish request confirmed
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

        // last trick undo request
        $(document).on('click', '#menu_request_undo', function () {
            socket.emit('request-undo', {
                player_id: player_id,
                table_id: $(this).data('table_id')
            })
        })

        // last trick undo request confirmed
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

        // player wants to show cards from hand
        $(document).on('click', '#menu_request_show_hand', function () {
            socket.emit('request-show-hand', {
                player_id: player_id,
                table_id: $(this).data('table_id')
            })
        })

        // player show cards confirmed
        $(document).on('click', '#button_show_cards_yes', function () {
            socket.emit('show-cards', {
                player_id: player_id,
                table_id: $(this).data('table_id')
            })
        })

        // player wants to exchange cards (re/contra)
        $(document).on('click', '#menu_request_exchange', function () {
            socket.emit('request-exchange', {
                player_id: player_id,
                table_id: $(this).data('table_id')
            })
        })

        // player1 confirms intended exchange
        $(document).on('click', '#button_start_exchange_yes', function () {
            socket.emit('exchange-start', {
                player_id: player_id,
                table_id: $(this).data('table_id')
            })
        })

        // player 2 confirms exchange
        $(document).on('click', '#button_exchange_confirm_player2', function () {
            socket.emit('exchange-player2-ready', {
                player_id: player_id,
                table_id: $(this).data('table_id')
            })
        })

        // player2 does not want to exchange cards
        $(document).on('click', '#button_exchange_deny_player2', function () {
            socket.emit('exchange-player2-deny', {
                player_id: player_id,
                table_id: $(this).data('table_id')
            })
        })

        // finally send cards to be exchanged to peer player
        $(document).on('click', '#button_exchange_send_cards', function () {
            // only if enough cards are about to be sent
            if (exchange_min_cards <= $('#table').children('.game-card').length &&
                $('#table').children('.game-card').length <= exchange_max_cards) {

                // hide exchange button
                $(this).addClass('d-none')

                // get cards on table to check with server
                let cards_table_ids = []
                for (let card_table of $('#table').children('.game-card')) {
                    cards_table_ids.push($(card_table).data('id'))
                }
                // clear cards on table
                $('#table').children('.game-card').remove()
                // change to avoid more cards being put onto table
                cards_locked = true
                socket.emit('exchange-player-cards-to-server', {
                    player_id: player_id,
                    table_id: $(this).data('table_id'),
                    cards_table_ids: cards_table_ids
                })
            }
        })

    }
)