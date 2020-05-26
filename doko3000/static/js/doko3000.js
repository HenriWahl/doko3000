// globally used player_id
let player_id = ''
// for staying in sync with the game this is global
let turn_count = 0
// keep an eye on next player to know if turns are allowed or not
let current_player_id = ''
// lock dragging of cards while waiting for trick being claimed
let cards_locked = false

$(document).ready(function () {
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
        console.log(card, source, target, cards_locked)
        if (card.id == 'cards_stack') {
            dragging_cards.cancel(true)
        } else if (source.id == 'hand' && target.id == 'table' && player_id == current_player_id && !cards_locked) {
            console.log(card.id == 'cards_stack')
            $('#table').append(card)
            // add tooltip
            $(card).attr('title', player_id)
            socket.emit('played-card', {
                player_id: player_id,
                card_id: $(card).data('id'),
                card_name: $(card).data('name'),
                table_id: $(card).data('table_id')
            })
        } else if (source.id == 'hand' && target.id == 'hand') {
            // get cards order to end it to server for storing it
            // let cards_hand = $('#hand').children('.game-card-hand')
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
        } else if (source.id == 'table' || cards_locked || player_id != current_player_id) {
            dragging_cards.cancel(true)
        }
    })

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
        if (msg.round_finished) {
            socket.emit('need-final-result', {
                player_id: player_id,
                table_id: msg.table_id
            })
        }
    })

    socket.on('new-table-available', function (msg) {
        $('#list_tables').html(msg.html)
    })

    socket.on('played-card-by-user', function (msg) {
        current_player_id = msg.current_player_id
        console.log(msg)
        //$('#hud_players').html('')
        $('#hud_players').html(msg.html.hud_players)
        $('.overlay-button').addClass('d-none')

        // $('.hud_player').removeClass('hud-player-active')
        // if (!msg.is_last_turn) {
        //     $('#hud_player_' + msg.current_player_id).addClass('hud-player-active')
        // }
        if (player_id != msg.player_id) {
            $('#table').append(msg.html.card)
            $('#card_' + msg.card_id).attr('title', msg.player_id)
        }
        if (msg.is_last_turn) {
            cards_locked = true
            $('#turn_indicator').addClass('d-none')
            console.log(msg.idle_players.includes(player_id))
            if (!msg.idle_players.includes(player_id)) {
                $('#button_claim_trick').removeClass('d-none')
            }
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
        socket.emit('my-cards-please', {
            player_id: player_id,
            table_id: msg.table_id
        })
    })

    socket.on('your-cards-please', function (msg) {
        current_player_id = msg.current_player_id
        cards_locked = false
        console.log('your-cards-please')
        $('#table').html('')
        $('#hud_players').html(msg.html.hud_players)
        $('#hand').html(msg.html.cards_hand)
        $('#button_claim_trick').addClass('d-none')
        $('#modal_dialog').modal('hide')
        console.log(msg)
        console.log(player_id, current_player_id)
        if (player_id == current_player_id) {
            $('#turn_indicator').removeClass('d-none')
        } else {
            $('#turn_indicator').addClass('d-none')
        }
        if (player_id == msg.dealer) {
            $('#button_deal_cards_again').removeClass('d-none')
        } else {
            $('#button_deal_cards_again').addClass('d-none')
        }
    })

    socket.on('sorry-no-cards-for-you', function (msg) {
        $('#table').html('')
        $('#hand').html('')
        $('#hud_players').html(msg.html.hud_players)
    })

    socket.on('really-deal-again', function (msg) {
        $('.overlay-notification').addClass('d-none')
        $('#modal_body').html(msg.html)
        $("#modal_dialog").modal('show')
    })

    socket.on('next-trick', function (msg) {
        current_player_id = msg.current_player_id
        console.log(msg)
        cards_locked = false
        $('#table').html('')
        // $('.hud_player').removeClass('hud-player-active')
        if (player_id == current_player_id) {
            $('#turn_indicator').removeClass('d-none')
        } else {
            $('#turn_indicator').addClass('d-none')
            // $('#hud_player_' + current_player_id).addClass('hud-player-active')
        }
        $('#hud_players').html(msg.html.hud_players)
        console.log(msg.score)
        console.log(player_id in msg.score)
        if (player_id in msg.score) {
            console.log(msg.score[player_id])
            $('#cards_stack').attr('title', msg.score[player_id])
            $('#cards_stack').removeClass('d-none')
        } else {
            $('#cards_stack').addClass('d-none')
        }
    })

    socket.on('round-finished', function (msg) {
        console.log('round-finished', msg)
        $('#button_claim_trick').addClass('d-none')
        // cleanup content of dialog
        $('#modal_body').html(msg.html)
        $("#modal_dialog").modal('show')
    })

    socket.on('start-next-round', function (msg) {
        console.log('start-next-round', msg)
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
        console.log('round-reset-requested', msg)
        $('.overlay-button').addClass('d-none')
        $('.overlay-notification').addClass('d-none')
        // cleanup content of dialog
        $('#modal_body').html(msg.html)
        $('#modal_dialog').modal('show')
    })

    socket.on('round-finish-requested', function (msg) {
        console.log('round-finish-requested', msg)
        $('.overlay-button').addClass('d-none')
        $('.overlay-notification').addClass('d-none')
        // cleanup content of dialog
        $('#modal_body').html(msg.html)
        $('#modal_dialog').modal('show')
    })

    socket.on('round-restart-options', function (msg) {
        console.log('round-restart-requested', msg)
        $('.overlay-button').addClass('d-none')
        $('.overlay-notification').addClass('d-none')
        // cleanup content of dialog
        $('#modal_body').html(msg.html)
        $('#modal_dialog').modal('show')
    })

    $(document).on('click', '#new_table', function () {
        socket.emit('new-table', {button: 'new_table'})
    })

    $(document).on('click', '.button-enter-table', function () {
        console.log($(this).data('table_players'), $(this).data('table_locked'))
        socket.emit('enter-table', {
            player_id: player_id,
            table_id: $(this).data('table_id')
        })
        // ask server via json if player is allowed to enter or not
        return $.getJSON('/table/enter/' + $(this).data('table_id') + '/' + player_id,
            function (data, status) {
                if (status == 'success') {
                    if (data.allowed) {
                        return data.allowed
                    }
                    return false
                }
                // dummy return just in case
                return false
            })
        // console.log(allowed)
        // return allowed
    })

    // draggable list of players in setup table dialog
    $(document).on('click', '.button-setup-table', function () {
        $.getJSON('/table/setup/' + $(this).data('table_id'), function (data, status) {
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

    // delete a player in the draggable players order
    $(document).on('click', '.button-remove-player-from-table', function () {
        console.log('remove player', $(this).data('player_id'))
        if (player_id != $(this).data('player_id')) {
            // used too if player leaves table via menu
            socket.emit('setup-table-change', {
                action: 'delete_player',
                player_id: $(this).data('player_id'),
                table_id: $(this).data('table_id')
            })
            $('.table_' + $(this).data('table_id') + '_player_' + $(this).data('player_id')).remove()
        }
    })

    $(document).on('click', '#button_deal_cards', function () {
        console.log('button_deal_cards')
        socket.emit('deal-cards', {
            player_id: player_id,
            table_id: $(this).data('table_id')
        })
    })

    $(document).on('click', '#button_start_table', function () {
        socket.emit('setup-table-change', {
            action: 'start_table',
            player_id: player_id,
            table_id: $(this).data('table_id')
        })
    })

    // reload page after setup
    $(document).on('click', '#button_finish_table_setup', function () {
        // location.reload()
        $.get('/get/html/tables',
            function (data, status) {
                console.log(data, status)
                if (status == 'success') {
                          $('#list_tables').html(data)
                }
            })
    })

    $(document).on('click', '#button_deal_cards_again', function () {
        console.log('button_deal_cards_again')
        socket.emit('deal-cards-again', {
            player_id: player_id,
            table_id: $(this).data('table_id')
        })
    })

    $(document).on('click', '#button_claim_trick', function () {
        console.log('claim trick')
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
        console.log('request_round_reset')
        socket.emit('request-round-reset', {
            player_id: player_id,
            table_id: $(this).data('table_id')
        })
    })

    $(document).on('click', '#button_round_reset_yes', function () {
        socket.emit('ready-for-round-reset', {
            player_id: player_id,
            table_id: $(this).data('table_id')
        })
    })

    $(document).on('click', '#menu_request_round_finish', function () {
        socket.emit('request-round-finish', {
            player_id: player_id,
            table_id: $(this).data('table_id')
        })
    })

    $(document).on('click', '#button_round_finish_yes', function () {
        console.log('button ready finish reset')
        socket.emit('ready-for-round-finish', {
            player_id: player_id,
            table_id: $(this).data('table_id')
        })
    })

    $(document).on('click', '#button_round_restart_yes', function () {
        console.log('button ready restart')
        socket.emit('ready-for-round-restart', {
            player_id: player_id,
            table_id: $(this).data('table_id')
        })
    })
})