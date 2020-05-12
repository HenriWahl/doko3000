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

    let dragging = dragula([document.querySelector('#hand'),
        document.querySelector('#table'), {
            revertOnSpill: true,
            direction: 'horizontal'
        }
    ]);

    dragging.on('drop', function (card, target, source) {
        // do not drag your gained tricks around
        console.log(card, source, target, cards_locked)
        if (card.id == 'cards_stack') {
            dragging.cancel(true)
        } else if (source.id == 'hand' && target.id == 'table' && player_id == current_player_id && !cards_locked) {
            console.log(card.id == 'cards_stack')
            $('#table').append(card)
            // add tooltip
            $(card).attr('title', player_id)
            socket.emit('played-card', {
                player_id: player_id,
                card_id: $(card).data('id'),
                card_name: $(card).data('name'),
                table: $(card).data('table')
            })
        } else if (source.id == 'hand' && target.id == 'hand') {
            return true
        } else if (source.id == 'table' || cards_locked || player_id != current_player_id) {
            dragging.cancel(true)
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
    })

    socket.on('new-table-available', function (msg) {
        $('#list_tables').html(msg.html)
    })

    socket.on('played-card-by-user', function (msg) {
        current_player_id = msg.current_player_id
        console.log(msg)
        // $('#hud_players').html('')
        // $('#hud_players').html(msg.html.hud_players)
        $('.hud_player').removeClass('hud_player_active')
        if (!msg.is_last_turn) {
            $('#hud_player_' + msg.current_player_id).addClass('hud_player_active')
        }
        if (player_id != msg.player_id) {
            $('#table').append(msg.html.card)
            $('#card_' + msg.card_id).attr('title', msg.player_id)
        }
        if (msg.is_last_turn) {
            cards_locked = true
            $('#turn_indicator').addClass('d-none')
            $('#claim_trick').removeClass('d-none')
        } else {
            cards_locked = false
            if (player_id == current_player_id) {
                $('#turn_indicator').removeClass('d-none')
            } else {
                $('#turn_indicator').addClass('d-none')
            }
            $('#claim_trick').addClass('d-none')
        }

        // $('#card_' + msg.card_id).attr('alt', msg.username)

        // anyway there is no need anymore to deal cards
        $('#deal_cards').addClass('d-none')
    })

    socket.on('grab-your-cards', function (msg) {
        socket.emit('my-cards-please', {
            player_id: player_id,
            table: msg.table
        })
    })

    socket.on('your-cards-please', function (msg) {
        current_player_id = msg.current_player_id
        cards_locked = false
        $('#table').html('')
        $('#hud_players').html(msg.html.hud_players)
        $('#hand').html(msg.html.cards_hand)
        $('#claim_trick').addClass('d-none')
        console.log(msg)
        console.log(player_id, current_player_id)
        if (player_id == current_player_id) {
            $('#turn_indicator').removeClass('d-none')
        } else {
            $('#turn_indicator').addClass('d-none')
        }
        if (player_id == msg.dealer) {
            $('#deal_cards').removeClass('d-none')
        } else {
            $('#deal_cards').addClass('d-none')
        }
    })

    socket.on('next-trick', function (msg) {
        current_player_id = msg.current_player_id
        console.log(msg)
        cards_locked = false
        $('#table').html('')
        $('.hud_player').removeClass('hud_player_active')
        if (player_id == current_player_id) {
            $('#turn_indicator').removeClass('d-none')
        } else {
            $('#turn_indicator').addClass('d-none')
            $('#hud_player_' + current_player_id).addClass('hud_player_active')
        }
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
        $('#claim_trick').addClass('d-none')
        // $('#next_round').removeClass('d-none')
        $('#modal_title').html('<strong>Runde beendet</strong>')
        // Inhalt des Dialogs erst einmal leeren, damit keine alten Reste darin kleben
        $('#modal_body').html(msg.html)
        $("#modal_dialog").modal()
    })

    socket.on('start-next-round', function (msg) {
        console.log(msg)
        if (player_id == msg.dealer) {
            $('#deal_cards').removeClass('d-none')
        } else {
            $('#deal_cards').addClass('d-none')
        }
        $('#next_round').addClass('d-none')
        $('#claim_trick').addClass('d-none')

    })


    $(document).on('click', '#new_table', function () {
        socket.emit('new-table', {button: 'new_table'})
    })

    $(document).on('click', '.list-item-table', function () {
        socket.emit('enter-table', {
            player_id: player_id,
            table: $(this).data('table')
        })
    })

    $(document).on('click', '#deal_cards', function () {
        console.log('deal_cards')
        socket.emit('deal-cards', {
            player_id: player_id,
            table: $(this).data('table')
        })
    })

    $(document).on('click', '#claim_trick', function () {
        console.log('claim trick')
        socket.emit('claim-trick', {
            player_id: player_id,
            table: $(this).data('table')
        })
    })

    $(document).on('click', '#next_round', function () {
        console.log('next_round')
        $('#next_round').addClass('d-none')
        socket.emit('ready-for-next-round', {
            player_id: player_id,
            table: $(this).data('table')
        })
    })

    $(document).on('click', '#request_round_reset', function () {
        console.log('request_round_reset')
        socket.emit('request-round-reset', {
            player_id: player_id,
            table_id: $(this).data('table_id')
        })
    })

})